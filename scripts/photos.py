#!/usr/bin/env python3
"""Find freely-licensed photographs on Wikimedia Commons for catalogue records.

    python3 scripts/photos.py --limit 50 --dry-run     # try a sample, change nothing
    python3 scripts/photos.py                          # full run

The archive draws its own schematic for every component. Those are useful but
they are not photographs, and people identifying a part in hand want to see
the real thing. This finds a real photo where one demonstrably exists.

It is deliberately strict. A keyword search for "Intel Pentium II 300" happily
returns a photo of the Deschutes revision when the record is the Klamath, and
a wrong photo on a reference page is worse than no photo. So a candidate is
only accepted when the manufacturer and every distinguishing model token from
the record title appear in the image title, and it is rejected outright when
the image mentions a conflicting codename, revision, or capacity.

Only files under public-domain, CC0, CC-BY, or CC-BY-SA terms are kept, and
the licence plus author is recorded for attribution.

Results are written to hardware-archives/photos.json. Nothing is downloaded
and no page is edited; scripts/photos_apply.py does that separately.
"""

import argparse
import glob
import json
import os
import re
import sys
import time
import urllib.error
import urllib.parse
import urllib.request

API = "https://commons.wikimedia.org/w/api.php"
UA = "AlienCultistLabs-HardwareArchive/1.0 (static reference site; https://github.com/windows95br0)"
OUT = "hardware-archives/photos.json"

# Licences we may actually use, mapped to how they must be credited.
FREE = {
    "cc0": "CC0", "public domain": "Public domain", "pd": "Public domain",
    "cc-by-sa-4.0": "CC BY-SA 4.0", "cc-by-sa-3.0": "CC BY-SA 3.0",
    "cc-by-sa-2.5": "CC BY-SA 2.5", "cc-by-sa-2.0": "CC BY-SA 2.0",
    "cc-by-4.0": "CC BY 4.0", "cc-by-3.0": "CC BY 3.0",
    "cc-by-2.5": "CC BY 2.5", "cc-by-2.0": "CC BY 2.0",
    "cc-by-sa-1.0": "CC BY-SA 1.0", "attribution": "CC BY",
}

# Words that carry no identifying weight, so they must not count as a match.
NOISE = {
    "the", "and", "for", "with", "series", "edition", "version", "rev",
    "card", "drive", "disk", "module", "unit", "kit", "type", "class",
    "computer", "enclosure", "controller", "adapter", "board", "chip",
    "inch", "mhz", "ghz", "mb", "gb", "tb", "kb", "watt", "w", "bit",
    "pc", "pin", "port", "dual", "single", "high", "low", "mini", "micro",
}

# If the record says one of these and the image says a different one from the
# same group, they are different parts no matter how well the numbers line up.
CONFLICT_GROUPS = [
    {"klamath", "deschutes", "coppermine", "katmai", "tualatin", "mendocino", "willamette",
     "northwood", "prescott", "conroe", "yorkfield", "wolfdale", "nehalem", "sandy", "ivy",
     "haswell", "skylake", "kaby", "coffee", "comet", "rocket", "alder", "raptor"},
    {"barton", "thoroughbred", "palomino", "thunderbird", "spitfire", "applebred",
     "clawhammer", "newcastle", "venice", "manchester", "brisbane", "deneb", "thuban",
     "zambezi", "vishera", "summit", "pinnacle", "matisse", "vermeer", "raphael"},
    {"agp", "pci", "pcie", "isa", "vlb", "mca", "eisa"},
    {"sata", "nvme", "sas", "ide", "scsi", "pata", "usb"},
    {"ddr", "ddr2", "ddr3", "ddr4", "ddr5", "sdram", "edo", "rdram", "simm", "dimm", "sodimm"},
    # Mobile and desktop parts share a model number but are different products.
    {"m", "mobile", "laptop", "notebook", "desktop", "server", "embedded"},
    {"fh", "hh", "lp", "atx", "microatx", "miniitx", "flexatx"},
    # A roman-numeral generation marker ("Model I" vs "Model III") names a
    # different product even though every other word lines up.
    {"i", "ii", "iii", "iv", "v", "vi", "vii", "viii", "ix", "x", "xi", "xii"},
    # Blackmagic Design's product-line names sit alongside shared words like
    # "4K" and "Pro" across entirely different physical products - DeckLink
    # is a capture card, HyperDeck is a standalone deck recorder, etc.
    {"decklink", "hyperdeck", "atem", "intensity", "ultrastudio", "teranex",
     "videohub", "smartview", "duet", "speededitor"},
]

# Fan/cooler suffix qualifiers - "P12 Pro PST LN" and "P12 Pro A-RGB" are
# different SKUs of the same base fan even though the model number matches.
# Checked one-sided (see suffix_mismatch below): an image explicitly labelled
# with one of these words is never a safe stand-in for an unlabelled base
# record, even though the reverse (a plain photo standing in for any SKU) is
# tolerated elsewhere in this file.
SUFFIX_QUALIFIERS = {"argb", "rgb", "pwm", "dc", "pst", "ln", "hs", "hp",
                      "bionix", "chromax", "redux", "industrial", "plus", "evo",
                      "led", "x2", "se", "turbo", "ultra", "mk2",
                      "v2", "black", "white", "gold", "silver", "edition",
                      "xt", "ti", "ks", "kf", "x3d", "aqua", "vega"}


def suffix_mismatch(record_title, image_title):
    """True when the image names a suffix SKU the record's title does not.

    Some of these words ("edition") are filtered out of significant() as
    noise for ordinary overlap scoring, but they still have to be compared
    here, so this re-tokenises the raw titles rather than reusing `want`.
    """
    rhit = set(tokens(record_title)) & SUFFIX_QUALIFIERS
    ihit = set(tokens(image_title)) & SUFFIX_QUALIFIERS
    return bool(ihit - rhit)

# A part's physical kind - a case photo must not stand in for a motherboard
# photo (or vice versa) just because the model number matches. Unlike
# CONFLICT_GROUPS, each inner set here is a group of synonyms for the SAME
# kind of object, so synonyms never conflict with each other; only a hit in
# one set against a hit in a *different* set counts as a mismatch.
PHYSICAL_KIND_GROUPS = [
    {"case", "enclosure", "chassis", "cabinet", "tower"},
    {"motherboard", "mainboard", "mobo"},
    {"keyboard"}, {"mouse"}, {"monitor", "display"}, {"speaker"}, {"headset"},
    {"webcam"}, {"joystick", "gamepad", "controller"}, {"scanner"}, {"printer"},
]


def category_mismatch(record_toks, image_toks):
    rset, iset = set(record_toks), set(image_toks)
    rcats = {i for i, g in enumerate(PHYSICAL_KIND_GROUPS) if rset & g}
    icats = {i for i, g in enumerate(PHYSICAL_KIND_GROUPS) if iset & g}
    return bool(rcats) and bool(icats) and not (rcats & icats)

TOKEN_RE = re.compile(r"[a-z0-9]+")
MODELISH = re.compile(r"^(?=.*\d)[a-z0-9\-]{2,}$")
# A long mixed letters-and-digits run like "3c509b" or "ct3990" names exactly one
# product, so it identifies a part on its own even without the maker's name.
DISTINCTIVE = re.compile(r"^(?=.*\d)(?=.*[a-z])[a-z0-9]{4,}$")


def tokens(text):
    # A trailing "+" names a distinct model ("Amiga 500+" vs "Amiga 500"), but
    # the token regex has no symbol class for it, so fold it into the token
    # text instead of silently dropping it and conflating the two parts.
    text = re.sub(r"(?<=[a-z0-9])\+", "plus", text, flags=re.I)
    return TOKEN_RE.findall(text.lower())


def significant(title):
    """Tokens that actually identify the part: brand words and model numbers."""
    out = []
    for tok in tokens(title):
        if tok in NOISE or len(tok) < 2:
            continue
        out.append(tok)
    return out


def model_tokens(title):
    """Tokens containing a digit - the part numbers and speeds that pin a model."""
    return [t for t in significant(title) if MODELISH.match(t)]


def conflicts(record_toks, image_toks):
    """True when record and image name different members of the same family."""
    rset, iset = set(record_toks), set(image_toks)
    for group in CONFLICT_GROUPS:
        rhit, ihit = rset & group, iset & group
        if rhit and ihit and not (rhit & ihit):
            return True
    return False


# "XP-M", "Athlon 64 Mobile", "-M 2500+" - a mobile part wears the same model
# number as its desktop twin, and single letters are dropped by significant(),
# so this is checked against the raw text instead of the token list.
MOBILE_RE = re.compile(r"\b(mobile|xp-m|-m\b|\bm\d|laptop|notebook|sodimm)\b", re.I)


def variant_mismatch(record_title, image_title):
    """True when one of the two is a mobile part and the other plainly is not."""
    return bool(MOBILE_RE.search(record_title)) != bool(MOBILE_RE.search(image_title))


ROMAN_VALUES = {"i": 1, "ii": 2, "iii": 3, "iv": 4, "v": 5, "vi": 6, "vii": 7,
                "viii": 8, "ix": 9, "x": 10, "xi": 11, "xii": 12}
MODEL_GEN_RE = re.compile(r"\bmodel\s+([ivxlcdm]+|\d+)\b", re.I)


def model_generation(text):
    """The number after the word "Model", normalised from roman numerals, so
    "Model III" and "Model 1" can be compared on equal footing."""
    found = MODEL_GEN_RE.search(text.lower())
    if not found:
        return None
    val = found.group(1)
    return int(val) if val.isdigit() else ROMAN_VALUES.get(val)


def generation_mismatch(record_title, image_title):
    """True when both name a "Model N" but N differs (TRS-80 Model I vs III)."""
    rg, ig = model_generation(record_title), model_generation(image_title)
    return rg is not None and ig is not None and rg != ig


def api_get(params, attempts=4):
    params = dict(params, format="json")
    url = API + "?" + urllib.parse.urlencode(params)
    for attempt in range(attempts):
        try:
            req = urllib.request.Request(url, headers={"User-Agent": UA})
            with urllib.request.urlopen(req, timeout=30) as resp:
                return json.load(resp)
        except urllib.error.HTTPError as err:
            if err.code in (429, 503):
                time.sleep(3 * (attempt + 1))
                continue
            return None
        except Exception:
            time.sleep(1.5 * (attempt + 1))
    return None


def search(term, limit=8):
    data = api_get({
        "action": "query", "list": "search", "srsearch": term + " filetype:bitmap",
        "srnamespace": "6", "srlimit": str(limit),
    })
    if not data:
        return []
    return [h["title"] for h in data.get("query", {}).get("search", [])]


def image_info(titles):
    """Licence, author and dimensions for a batch of File: titles."""
    if not titles:
        return {}
    data = api_get({
        "action": "query", "titles": "|".join(titles), "prop": "imageinfo",
        "iiprop": "url|extmetadata|size", "iiurlwidth": "900",
    })
    if not data:
        return {}
    out = {}
    for page in data.get("query", {}).get("pages", {}).values():
        info = (page.get("imageinfo") or [{}])[0]
        if not info:
            continue
        meta = info.get("extmetadata", {})
        out[page["title"]] = {
            "licence_raw": (meta.get("LicenseShortName", {}).get("value")
                            or meta.get("License", {}).get("value") or ""),
            "author": re.sub(r"<[^>]+>", "", meta.get("Artist", {}).get("value", "")).strip(),
            "descr_url": info.get("descriptionurl", ""),
            "thumb": info.get("thumburl", ""),
            "width": info.get("thumbwidth"), "height": info.get("thumbheight"),
        }
    return out


def licence_ok(raw):
    """Map a Commons licence string to how we must credit it, or None if unusable.

    Commons writes these inconsistently ("CC BY-SA 4.0", "cc-by-sa-4.0",
    "CC-BY-SA-4.0"), so flatten separators before comparing.
    """
    low = re.sub(r"[\s_-]+", "", raw.lower())
    if not low:
        return None
    for key, label in FREE.items():
        if re.sub(r"[\s_-]+", "", key) in low:
            return label
    return None


def best_match(title, candidates, info):
    """The single strongest candidate, or None when nothing is convincing."""
    want = significant(title)
    want_models = model_tokens(title)
    brand = want[0] if want else ""
    scored = []
    for cand in candidates:
        meta = info.get(cand)
        if not meta:
            continue
        licence = licence_ok(meta["licence_raw"])
        if not licence:
            continue
        name = cand[5:].rsplit(".", 1)[0]  # strip "File:" and extension
        itoks = tokens(name)
        iset = set(itoks)
        # A unique part number carries the identification by itself; otherwise
        # the manufacturer has to be named.
        strong = [m for m in want_models if DISTINCTIVE.match(m) and m in iset]
        if brand and brand not in iset and not strong:
            continue
        # Every model number in the record has to appear in the image title.
        if want_models and not all(m in iset for m in want_models):
            continue
        # A record with no model number is too vague to match safely.
        if not want_models:
            continue
        if conflicts(want, itoks):
            continue
        if variant_mismatch(title, name):
            continue
        if category_mismatch(want, itoks):
            continue
        if generation_mismatch(title, name):
            continue
        if suffix_mismatch(title, name):
            continue
        overlap = len([t for t in want if t in iset])
        scored.append((overlap / len(want), cand, licence, meta))
    if not scored:
        return None
    scored.sort(key=lambda s: -s[0])
    ratio, cand, licence, meta = scored[0]
    # A distinctive part number is proof on its own; otherwise most of the
    # identifying words have to line up.
    floor = 0.34 if any(DISTINCTIVE.match(m) for m in want_models) else 0.5
    if ratio < floor:
        return None
    return {
        "file": cand, "licence": licence, "author": meta["author"],
        "page": meta["descr_url"], "thumb": meta["thumb"],
        "width": meta["width"], "height": meta["height"], "confidence": round(ratio, 3),
    }


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--limit", type=int, default=0, help="only try this many records")
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--category", help="restrict to one archive category")
    ap.add_argument("--resume", action="store_true", help="keep existing photos.json hits")
    args = ap.parse_args()

    if not os.path.exists("style.css"):
        sys.exit("run this from the repo root")

    records = []
    for path in sorted(glob.glob("hardware-archives/**/components/*/index.html", recursive=True)):
        category = path.split("/")[1]
        if args.category and category != args.category:
            continue
        html = open(path, encoding="utf-8").read()
        found = re.search(r"<h1>(.*?)</h1>", html, re.S)
        if found:
            records.append({
                "file": path, "category": category,
                "title": re.sub(r"<[^>]+>", "", found.group(1)).strip(),
            })

    have = {}
    if args.resume and os.path.exists(OUT):
        have = json.load(open(OUT))
    todo = [r for r in records if r["file"] not in have]
    if args.limit:
        todo = todo[:args.limit]

    print("records %d | already matched %d | trying %d\n" % (len(records), len(have), len(todo)))
    claimed = {v["file"]: k for k, v in have.items()}
    hits = 0
    for i, rec in enumerate(todo, 1):
        cands = search(rec["title"])
        match = best_match(rec["title"], cands, image_info(cands)) if cands else None
        # One photo cannot depict two different parts. If a file is already
        # claimed, one of the two matches must be wrong, so keep neither.
        if match and match["file"] in claimed:
            other = claimed[match["file"]]
            if other in have:
                print("  DROP %s - image already used by %s"
                      % (rec["title"][:40], have[other]["title"][:40]))
                del have[other]
            match = None
        if match:
            hits += 1
            claimed[match["file"]] = rec["file"]
            have[rec["file"]] = dict(match, title=rec["title"], category=rec["category"])
            print("  HIT  %-52s %s [%s]" % (rec["title"][:52], match["file"][5:60], match["licence"]))
        if i % 25 == 0:
            print("  ... %d/%d checked, %d matched" % (i, len(todo), hits))
            if not args.dry_run:
                json.dump(have, open(OUT, "w"), indent=1, sort_keys=True)
        time.sleep(1.5)

    print("\nchecked %d, matched %d (%.1f%%)"
          % (len(todo), hits, 100.0 * hits / len(todo) if todo else 0))
    if args.dry_run:
        print("dry run - nothing written")
    else:
        json.dump(have, open(OUT, "w"), indent=1, sort_keys=True)
        print("wrote", OUT, "with", len(have), "entries")


if __name__ == "__main__":
    main()
