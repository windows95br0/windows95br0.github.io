#!/usr/bin/env python3
"""Build the browse-by pivot pages for the hardware archive.

    python3 scripts/pivots.py

Every established hardware reference organises the same way: what a thing *is*
decides the tree, and who made it, what it plugs into and when it shipped are
filters laid across that tree. PCPartPicker, The Retro Web and VOGONS all do
this; iFixit is the counter-example, having baked the vendor into its node
names and ended up with "western digital hard drive" sitting next to "Toshiba
Hard Drive".

This archive already gets the tree right, but until now the only way in was
through that tree. These generated pages add the missing axes:

    hardware-archives/manufacturers/            every maker, A-Z
    hardware-archives/manufacturers/<slug>/     one maker, grouped by type
    hardware-archives/interfaces/               every connection type
    hardware-archives/interfaces/<slug>/        everything using it
    hardware-archives/storage/                  all storage by media type

Existing URLs are untouched. These are additional ways in, not a move.
"""

import glob
import html
import json
import os
import re
import sys
from collections import defaultdict

ROOT = "hardware-archives"

# Makers whose names run to more than one word, longest first so that
# "Western Digital" wins before "Western" can match.
MULTIWORD = [
    "Western Digital", "Cooler Master", "Fractal Design", "be quiet!", "Lian Li",
    "SK hynix", "Thermal Grizzly", "Silicon Power", "Smart App", "Team Group",
    "Super Flower", "Deep Cool", "In Win", "Sea Sonic", "Patriot Memory",
    "G.Skill", "Mushkin Enhanced", "Kingston Technology", "Micro Center",
    "Cable Matters", "Monoprice Select", "Startech Com",
    "CH Products", "I-O DATA", "Universal Audio", "Silicon Graphics",
    "Diamond Multimedia", "Number Nine", "Media Vision", "Turtle Beach",
    "Y-E Data", "PC Chips",
]

# Leading words that describe the thing rather than name its maker. A title
# like "ATX 24-pin Motherboard Power Cable" or "DDR4 ECC UDIMM" starts with a
# standard, not a company, and must not create a manufacturer page.
NOT_VENDORS = {
    "atx", "sfx", "tfx", "eps", "usb", "pci", "pcie", "sata", "sas", "ide",
    "scsi", "pata", "esdi", "mfm", "rll", "ddr", "ddr2", "ddr3", "ddr4",
    "ddr5", "sdram", "simm", "dimm", "sodimm", "rdimm", "udimm", "edo",
    "agp", "isa", "vlb", "mca", "eisa", "nvme", "m.2", "msata", "u.2",
    "ps/2", "vga", "dvi", "hdmi", "displayport", "thunderbolt", "firewire",
    "ethernet", "generic", "universal", "standard", "external", "internal",
    "dual", "single", "micro", "mini", "full", "half", "high", "low",
    "compactflash", "smartmedia", "memorystick", "xd", "sd", "microsd",
    "atx12v", "eps12v", "dvi-d", "dvi-i", "dvi-a", "usb-c", "usb-a",
    "usb-b", "rs-232", "rs232", "rs-422", "rs-485", "pc", "db-9", "de-9",
    "db-25", "de-15", "centronics", "s-video", "spdif", "s/pdif",
    "9sx", "z220",
}

# Names that mean the same company written differently.
ALIASES = {
    "nvidia": "NVIDIA", "ati": "ATI", "amd": "AMD", "intel": "Intel",
    "hp": "HP", "hpe": "HPE", "ibm": "IBM", "wd": "Western Digital",
    "gigabyte": "GIGABYTE", "asus": "ASUS", "msi": "MSI", "evga": "EVGA",
    "ocz": "OCZ", "pny": "PNY", "xfx": "XFX", "lg": "LG", "nec": "NEC",
    "tdk": "TDK", "3m": "3M", "apc": "APC", "aoc": "AOC", "elo": "Elo",
    "startech": "StarTech", "startech com": "StarTech", "tp link": "TP-Link",
    "netgear": "NETGEAR", "arctic": "ARCTIC", "adata": "ADATA",
    "sandisk": "SanDisk", "seagate": "Seagate", "samsung": "Samsung",
    "toshiba": "Toshiba", "crucial": "Crucial", "corsair": "Corsair",
    "3dfx": "3dfx", "3com": "3Com", "3dconnexion": "3Dconnexion",
}

# Connection types worth pivoting on, matched against the record text.
# Order matters: the more specific label has to be tried first.
INTERFACES = [
    ("PCIe 5.0", r"\bpcie?\s*5\.0\b|\bgen\s*5\b"),
    ("PCIe 4.0", r"\bpcie?\s*4\.0\b|\bgen\s*4\b"),
    ("PCIe 3.0", r"\bpcie?\s*3\.0\b|\bgen\s*3\b"),
    ("PCIe 2.0", r"\bpcie?\s*2\.0\b"),
    ("PCIe 1.x", r"\bpcie?\s*1\.[01]\b"),
    ("NVMe", r"\bnvme\b"),
    ("M.2", r"\bm\.?2\b"),
    ("mSATA", r"\bmsata\b"),
    ("U.2", r"\bu\.2\b"),
    ("SATA", r"\bsata\b"),
    ("SAS", r"\bsas\b"),
    ("SCSI", r"\bscsi\b|\bultra\s*wide\b"),
    ("PATA / IDE", r"\bpata\b|\bide\b|\beide\b|\batapi\b"),
    ("ST-506 / MFM", r"\bst-?506\b|\bmfm\b|\brll\b"),
    ("ESDI", r"\besdi\b"),
    ("AGP", r"\bagp\b"),
    ("PCI", r"\bpci\b(?!e)"),
    ("ISA", r"\bisa\b"),
    ("VESA Local Bus", r"\bvlb\b|\bvesa local\b"),
    ("MCA", r"\bmicro\s*channel\b|\bmca\b"),
    ("USB", r"\busb\b"),
    ("Thunderbolt", r"\bthunderbolt\b"),
    ("FireWire", r"\bfirewire\b|\bieee\s*1394\b"),
    ("Ethernet", r"\bethernet\b|\b10base\b|\b100base\b|\b1000base\b"),
    ("Fibre Channel", r"\bfibre channel\b|\bfiber channel\b"),
    ("Serial / RS-232", r"\brs-?232\b|\bserial port\b"),
    ("Parallel / LPT", r"\bparallel port\b|\blpt\b|\bcentronics\b"),
    ("PS/2", r"\bps/2\b"),
    ("Slot 1", r"\bslot\s*1\b"),
    ("Socket 7", r"\bsocket\s*7\b"),
    ("Socket 370", r"\bsocket\s*370\b"),
    ("Socket AM4", r"\bam4\b"),
    ("Socket AM5", r"\bam5\b"),
    ("LGA 1700", r"\blga\s*1700\b"),
    ("LGA 1200", r"\blga\s*1200\b"),
    ("LGA 1151", r"\blga\s*1151\b"),
]

# How the archive's directories group by what the media physically is, which
# is the split every reference site agrees on. Interface is deliberately not
# used here - a drive ships in SATA and SAS, so it cannot define the shelf.
STORAGE_GROUPS = [
    ("Solid-state drives", "Flash storage, whatever it plugs into.",
     ["nvme-ssds", "sata-ssds", "sas-ssds"]),
    ("Hard disk drives", "Rotating magnetic platters, MFM through modern SATA.",
     ["hard-drives"]),
    ("Optical drives", "CD, DVD, Blu-ray readers and writers.",
     ["optical-drives"]),
    ("Floppy drives", "8-inch, 5.25-inch and 3.5-inch mechanisms, plus emulators.",
     ["floppy-drives"]),
    ("Removable media", "Cartridges, tape, flash cards and the drives that read them.",
     ["removable-media"]),
]

# Filled in from each category's own <h1>. Seeded where that heading is
# hyphenated purely for the two-line display treatment.
CATEGORY_LABELS = {"motherboards": "Motherboards"}


def slugify(name):
    s = re.sub(r"[^a-z0-9]+", "-", name.lower()).strip("-")
    return s or "other"


def esc(text):
    return html.escape(text, quote=True)


def read_records():
    """Every component page, with the facets we can trust from its own text."""
    records = []
    for path in sorted(glob.glob(ROOT + "/**/components/*/index.html", recursive=True)):
        raw = open(path, encoding="utf-8").read()
        title_m = re.search(r"<h1>(.*?)</h1>", raw, re.S)
        if not title_m:
            continue
        title = html.unescape(re.sub(r"<[^>]+>", "", title_m.group(1))).strip()
        category = path.split("/")[1]
        text = html.unescape(re.sub(r"<[^>]+>", " ", raw))
        records.append({
            "path": path, "url": os.path.dirname(path), "title": title,
            "category": category, "vendor": vendor_of(title),
            "interfaces": interfaces_of(text),
        })
    return records


def vendor_of(title):
    for name in sorted(MULTIWORD, key=len, reverse=True):
        if title.lower().startswith(name.lower()):
            return name
    first = title.split()[0] if title.split() else "Other"
    first = first.strip("(),")
    key = first.lower()
    if key in ALIASES:
        return ALIASES[key]
    # A leading part number is not a maker's name.
    if re.match(r"^[0-9.]+$", first) or len(first) < 2:
        return "Other"
    # Nor is a leading standard, bus or form factor.
    if key in NOT_VENDORS or re.match(r"^\d+-(pin|bit|way)$", key):
        return "Other"
    # Memory speed grades such as "DDR2-800" or "PC3-10600" name a standard.
    if re.match(r"^(ddr\d?|pc\d?|lpddr\d?)-?\d+$", key):
        return "Other"
    return first


def interfaces_of(text):
    low = text.lower()
    found = []
    for label, pattern in INTERFACES:
        if re.search(pattern, low):
            found.append(label)
    return found


def category_label(category):
    """The archive's own name for a category, taken from its index page."""
    if category in CATEGORY_LABELS:
        return CATEGORY_LABELS[category]
    index = os.path.join(ROOT, category, "index.html")
    label = category.replace("-", " ").title()
    if os.path.exists(index):
        found = re.search(r"<h1>(.*?)</h1>", open(index, encoding="utf-8").read(), re.S)
        if found:
            raw = found.group(1)
            # Headings are split for display, e.g. "Hard disk<br><span>drives.</span>".
            # A line broken mid-word keeps its hyphen; anything else needs a space.
            raw = re.sub(r"-\s*<br\s*/?>", "-", raw)
            raw = re.sub(r"<br\s*/?>", " ", raw)
            label = html.unescape(re.sub(r"<[^>]+>", "", raw))
            label = re.sub(r"\s+", " ", label).strip().rstrip(".")
    CATEGORY_LABELS[category] = label
    return label


def page(depth, title, description, eyebrow, heading, intro, body, crumb):
    """One archive page, matching the markup the rest of the site already uses."""
    up = "../" * depth
    canon = "https://windows95br0.github.io/" + crumb
    return """<!doctype html>
<html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1"><meta name="description" content="{desc}"><title>{title} // Hardware Archives</title><link rel="canonical" href="{canon}"><meta property="og:type" content="website"><meta property="og:site_name" content="Hardware Archives // Alien Cultist Labs"><meta property="og:title" content="{title} // Hardware Archives"><meta property="og:description" content="{desc}"><meta property="og:url" content="{canon}"><meta property="og:image" content="https://windows95br0.github.io/assets/images/og-hardware.jpg"><meta property="og:image:width" content="1200"><meta property="og:image:height" content="630"><meta property="og:image:alt" content="Alien Cultist Labs"><meta name="twitter:card" content="summary_large_image"><meta name="twitter:title" content="{title} // Hardware Archives"><meta name="twitter:description" content="{desc}"><meta name="twitter:image" content="https://windows95br0.github.io/assets/images/og-hardware.jpg"><meta name="theme-color" content="#040912"><link rel="icon" href="{up}assets/favicon.svg" type="image/svg+xml"><link rel="stylesheet" href="{up}style.css"><link rel="stylesheet" href="{arch}archive.css"></head>
<body class="hardware-page"><div class="site-shell"><header class="topbar" id="top"><a class="brand" href="{up}index.html" aria-label="Alien Cultist Labs home"><span class="brand-wordmark">ALIENCULTIST.COM</span></a><div class="status-line"><span class="status-dot"></span> HARDWARE ARCHIVES <span class="status-divider">//</span> {eyebrow}</div><nav class="main-nav" aria-label="Archive navigation"><a href="{up}index.html">HOME</a><a href="{arch}index.html">ALL CATEGORIES</a><a href="{arch}manufacturers/index.html">MANUFACTURERS</a><a href="{arch}interfaces/index.html">INTERFACES</a><a class="search-nav-link" href="{up}search.html">SEARCH</a></nav></header>
<main class="hardware-record"><nav class="record-back"><a href="{arch}index.html">&larr; All categories</a><span>{eyebrow}</span></nav><section class="record-hero"><div><p class="eyebrow">[ {eyebrow} ]</p><h1>{heading}</h1><p class="record-intro">{intro}</p></div></section>
{body}</main>
<footer class="footer"><p>&copy; 2026 ALIEN CULTIST LABS // GALT, CALIFORNIA</p><a href="{arch}index.html">CATEGORY CATALOG</a><a href="#top">BACK TO TOP &uarr;</a></footer></div><script src="{up}scripts/site.js" defer></script>
</body></html>
""".format(desc=esc(description), title=esc(title), canon=canon, up=up,
           arch=up + ROOT + "/", eyebrow=esc(eyebrow), heading=esc(heading),
           intro=esc(intro), body=body)


def link_list(records, depth, group_by="category"):
    """Records grouped under headings, as plain linked lists."""
    groups = defaultdict(list)
    for rec in records:
        groups[rec[group_by]].append(rec)
    out = []
    for key in sorted(groups, key=lambda k: (-len(groups[k]), k)):
        items = sorted(groups[key], key=lambda r: r["title"].lower())
        label = category_label(key) if group_by == "category" else key
        out.append('<section class="record-section"><h2>%s <small>(%d)</small></h2><ul class="pivot-list">'
                   % (esc(label), len(items)))
        for rec in items:
            href = "../" * depth + rec["url"] + "/index.html"
            out.append('<li><a href="%s">%s</a></li>' % (esc(href), esc(rec["title"])))
        out.append("</ul></section>")
    return "\n".join(out)


def write(path, content):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8") as fh:
        fh.write(content)


def build_manufacturers(records):
    by_vendor = defaultdict(list)
    for rec in records:
        by_vendor[rec["vendor"]].append(rec)
    # A single record does not make a manufacturer page worth having.
    keep = {v: rs for v, rs in by_vendor.items() if len(rs) >= 2 and v != "Other"}

    letters = defaultdict(list)
    for vendor in sorted(keep, key=str.lower):
        initial = vendor[0].upper()
        if not initial.isalpha():
            initial = "#"
        letters[initial].append(vendor)

    body = ['<section class="record-section"><p class="record-scope"><strong>{:,} manufacturers</strong> across {:,} catalogued parts. Makers with a single record are listed in their category instead.</p></section>'
            .format(len(keep), sum(len(v) for v in keep.values()))]
    for initial in sorted(letters):
        body.append('<section class="record-section"><h2>%s</h2><ul class="pivot-list pivot-cols">' % initial)
        for vendor in letters[initial]:
            body.append('<li><a href="%s/index.html">%s</a> <small>(%d)</small></li>'
                        % (esc(slugify(vendor)), esc(vendor), len(keep[vendor])))
        body.append("</ul></section>")
    write(os.path.join(ROOT, "manufacturers", "index.html"), page(
        2, "Manufacturers", "Every manufacturer represented in the hardware archive, A to Z, with a record count for each.",
        "MANUFACTURER INDEX", "Manufacturers",
        "Browse the archive by who built the part. Useful when the only thing you can read on a board is the maker's logo.",
        "\n".join(body), ROOT + "/manufacturers/"))

    for vendor, recs in keep.items():
        cats = sorted({category_label(r["category"]) for r in recs})
        intro = "%d catalogued %s from %s, grouped by component type." % (
            len(recs), "part" if len(recs) == 1 else "parts", vendor)
        body = ['<section class="record-section"><p class="record-scope"><strong>APPEARS IN:</strong> %s</p></section>'
                % esc(", ".join(cats))]
        body.append(link_list(recs, 3))
        write(os.path.join(ROOT, "manufacturers", slugify(vendor), "index.html"), page(
            3, vendor, "Every %s part catalogued in the hardware archive, grouped by component type." % vendor,
            "MANUFACTURER RECORD", vendor, intro, "\n".join(body),
            ROOT + "/manufacturers/" + slugify(vendor) + "/"))
    return len(keep)


def build_interfaces(records):
    by_iface = defaultdict(list)
    for rec in records:
        for iface in rec["interfaces"]:
            by_iface[iface].append(rec)
    keep = {i: rs for i, rs in by_iface.items() if len(rs) >= 3}

    body = ['<section class="record-section"><p class="record-scope">An interface is a property of a part, not a shelf to put it on: one drive model ships in SATA and SAS, and one M.2 slot carries either SATA or NVMe. These pages cut across the categories accordingly.</p></section>',
            '<section class="record-section"><h2>Connections and sockets</h2><ul class="pivot-list pivot-cols">']
    for iface in sorted(keep, key=lambda k: (-len(keep[k]), k)):
        body.append('<li><a href="%s/index.html">%s</a> <small>(%d)</small></li>'
                    % (esc(slugify(iface)), esc(iface), len(keep[iface])))
    body.append("</ul></section>")
    write(os.path.join(ROOT, "interfaces", "index.html"), page(
        2, "Interfaces", "Browse the hardware archive by interface, bus, socket or connector.",
        "INTERFACE INDEX", "Interfaces and buses",
        "Browse by what a part plugs into, across every category in the archive.",
        "\n".join(body), ROOT + "/interfaces/"))

    for iface, recs in keep.items():
        intro = "%d catalogued parts reference %s, across %d categories." % (
            len(recs), iface, len({r["category"] for r in recs}))
        write(os.path.join(ROOT, "interfaces", slugify(iface), "index.html"), page(
            3, iface, "Every part in the hardware archive that uses %s, grouped by component type." % iface,
            "INTERFACE RECORD", iface, intro, link_list(recs, 3),
            ROOT + "/interfaces/" + slugify(iface) + "/"))
    return set(keep)


def build_storage(records, linkable):
    body = ['<section class="record-section"><p class="record-scope">Storage is shelved here by what the media physically <em>is</em> &mdash; flash, platter, optical, magnetic &mdash; because that is the one split that stays true. How a drive connects is a property of the drive, so SATA, SAS and NVMe solid-state drives sit together and you filter by interface instead.</p></section>']
    for heading, blurb, cats in STORAGE_GROUPS:
        recs = [r for r in records if r["category"] in cats]
        if not recs:
            continue
        ifaces = sorted({i for r in recs for i in r["interfaces"] if i in linkable})
        body.append('<section class="record-section"><h2>%s <small>(%d)</small></h2><p>%s</p><ul class="pivot-list">'
                    % (esc(heading), len(recs), esc(blurb)))
        for cat in cats:
            in_cat = [r for r in recs if r["category"] == cat]
            if in_cat:
                body.append('<li><a href="../%s/index.html">%s</a> <small>(%d records)</small></li>'
                            % (esc(cat), esc(category_label(cat)), len(in_cat)))
        body.append("</ul>")
        if ifaces:
            links = ", ".join(
                '<a href="../interfaces/%s/index.html">%s</a>' % (slugify(i), esc(i))
                for i in ifaces[:14])
            body.append("<p><small><strong>INTERFACES SEEN HERE:</strong> %s</small></p>" % links)
        body.append("</section>")
    total = sum(len([r for r in records if r["category"] in cats])
                for _, _, cats in STORAGE_GROUPS)
    write(os.path.join(ROOT, "storage", "index.html"), page(
        2, "Storage", "All storage hardware in the archive, grouped by media technology, with interface as a filter.",
        "STORAGE OVERVIEW", "Storage",
        "{:,} storage records, shelved by media technology rather than by connector.".format(total),
        "\n".join(body), ROOT + "/storage/"))
    return total


def main():
    if not os.path.exists("style.css"):
        sys.exit("run this from the repo root")
    records = read_records()
    print("read %d component records" % len(records))
    vendors = build_manufacturers(records)
    ifaces = build_interfaces(records)
    storage = build_storage(records, ifaces)
    print("manufacturers  %d pages" % vendors)
    print("interfaces     %d pages" % len(ifaces))
    print("storage hub    %d records grouped" % storage)
    print("\nremember to run scripts/build.py so search and the sitemap pick these up")


if __name__ == "__main__":
    main()
