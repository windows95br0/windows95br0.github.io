#!/usr/bin/env python3
"""Attach the verified Wikimedia Commons photographs to their part records.

    python3 scripts/photos_apply.py [--limit N] [--dry-run]

scripts/photos.py does the finding and writes hardware-archives/photos.json.
This script does the applying: it downloads each accepted file, saves it beside
the record as photo.jpg, and swaps it in for the existing schematic <figure>.

Two things this script will not do:

  * It will not touch a record that already has a photo figure, so it is safe
    to re-run after photos.py finds more.
  * It will not insert a photo without its credit. Every Commons licence here
    requires attribution, so the caption always carries the author, the licence
    name, and a link back to the file page. If any of those are missing from
    the match, the record is skipped rather than published uncredited.

The original schematic is retired once a verified photograph is in place; it
was only ever a placeholder standing in for the real thing.
"""

import argparse
import html
import json
import os
import re
import sys
import time
import urllib.error
import urllib.request

from PIL import Image

ROOT = "hardware-archives"
MATCHES = os.path.join(ROOT, "photos.json")
UA = "AlienCultistLabs-archive/1.0 (https://windows95br0.github.io/; hardware archive illustration)"

# Commons file pages spell the licence in full; these are the short names we
# show and the URL for each, so a reader can check the terms for themselves.
LICENCES = {
    "cc0": ("CC0", "https://creativecommons.org/publicdomain/zero/1.0/"),
    "publicdomain": ("Public domain", ""),
    "ccby1.0": ("CC BY 1.0", "https://creativecommons.org/licenses/by/1.0/"),
    "ccby2.0": ("CC BY 2.0", "https://creativecommons.org/licenses/by/2.0/"),
    "ccby2.5": ("CC BY 2.5", "https://creativecommons.org/licenses/by/2.5/"),
    "ccby3.0": ("CC BY 3.0", "https://creativecommons.org/licenses/by/3.0/"),
    "ccby4.0": ("CC BY 4.0", "https://creativecommons.org/licenses/by/4.0/"),
    "ccbysa1.0": ("CC BY-SA 1.0", "https://creativecommons.org/licenses/by-sa/1.0/"),
    "ccbysa2.0": ("CC BY-SA 2.0", "https://creativecommons.org/licenses/by-sa/2.0/"),
    "ccbysa2.5": ("CC BY-SA 2.5", "https://creativecommons.org/licenses/by-sa/2.5/"),
    "ccbysa3.0": ("CC BY-SA 3.0", "https://creativecommons.org/licenses/by-sa/3.0/"),
    "ccbysa4.0": ("CC BY-SA 4.0", "https://creativecommons.org/licenses/by-sa/4.0/"),
    "ccby": ("CC BY", "https://creativecommons.org/licenses/by/4.0/"),
    "ccbysa": ("CC BY-SA", "https://creativecommons.org/licenses/by-sa/4.0/"),
}


def licence_parts(raw):
    """Short name and terms URL for a licence string, or None if unrecognised."""
    key = re.sub(r"[\s_-]+", "", (raw or "")).lower()
    return LICENCES.get(key)


def esc(text):
    return html.escape(str(text), quote=True)


def clean_author(raw):
    """Commons stores author as HTML. We want the name, not the markup."""
    text = re.sub(r"<[^>]+>", " ", raw or "")
    text = html.unescape(text)
    text = re.sub(r"\s+", " ", text).strip()
    return text.strip(" ,;|")


def fetch(url, tries=4):
    for attempt in range(tries):
        try:
            request = urllib.request.Request(url, headers={"User-Agent": UA})
            with urllib.request.urlopen(request, timeout=60) as response:
                return response.read()
        except urllib.error.HTTPError as err:
            if err.code in (429, 503) and attempt < tries - 1:
                time.sleep(2 ** attempt)
                continue
            raise
        except Exception:
            if attempt < tries - 1:
                time.sleep(2 ** attempt)
                continue
            raise
    return None


def shrink(path, longest=760):
    """Resize a downloaded photo to something the page will actually use.

    The record shows these at roughly 340 pixels tall. Commons hands out a
    960 pixel thumbnail, which at full quality runs to two megabytes, and
    shipping that is a waste of a visitor's bandwidth and of this repository.
    760 on the long edge still looks sharp on a high-density screen.

    Returns the final (width, height).
    """
    with Image.open(path) as opened:
        opened = opened.convert("RGB")
        width, height = opened.size
        if max(width, height) > longest:
            scale = longest / float(max(width, height))
            width, height = int(round(width * scale)), int(round(height * scale))
            opened = opened.resize((width, height), Image.LANCZOS)
        opened.save(path, "JPEG", quality=82, optimize=True, progressive=True)
    return width, height


def figure_html(match, filename, width, height):
    """The photo figure, credit included. Returns None if it cannot be credited."""
    licence = licence_parts(match.get("licence"))
    author = clean_author(match.get("author"))
    page = match.get("page")
    if not licence or not page:
        return None
    name, terms = licence
    # CC0 and public domain images carry no attribution requirement, but naming
    # the photographer is the decent thing to do and costs nothing.
    if not author:
        author = "unknown photographer"

    size = ' width="%d" height="%d"' % (width, height) if width and height else ""

    alt = "Photograph of %s" % match.get("title", "this part")
    licence_link = ('<a href="%s" rel="license noopener" target="_blank">%s</a>'
                    % (esc(terms), esc(name))) if terms else esc(name)

    return (
        '<figure class="record-figure record-photo">'
        '<img class="record-art" src="%s" alt="%s" loading="lazy" decoding="async"%s>'
        '<figcaption>PHOTOGRAPH &mdash; %s, %s &middot; '
        '<a href="%s" rel="noopener" target="_blank">FILE ON WIKIMEDIA COMMONS</a>'
        '</figcaption></figure>'
        % (esc(filename), esc(alt), size, esc(author), licence_link, esc(page))
    )


def apply_one(path, match, dry_run):
    with open(path, encoding="utf-8") as handle:
        page = handle.read()

    if "record-photo" in page:
        return "already done"

    schematic = re.search(r'<figure class="record-figure">.*?</figure>', page, re.S)
    if not schematic:
        return "no figure to sit above"

    if not figure_html(match, "photo.jpg", 0, 0):
        return "cannot be credited"

    if dry_run:
        return "ok"

    try:
        data = fetch(match["thumb"])
    except Exception as err:
        return "download failed: %s" % err
    if not data or len(data) < 2048:
        return "download too small to be a photo"

    with open(os.path.join(os.path.dirname(path), "photo.jpg"), "wb") as handle:
        handle.write(data)

    # Commons reports the original file's dimensions, but we save the thumbnail,
    # which is a different size. Measure what we actually wrote so the width and
    # height attributes reserve the right space and no layout shift occurs.
    photo = os.path.join(os.path.dirname(path), "photo.jpg")
    try:
        real_width, real_height = shrink(photo)
    except Exception as err:
        os.remove(photo)
        return "not a readable image: %s" % err

    figure = figure_html(match, "photo.jpg", real_width, real_height)

    # The schematic was only ever a placeholder until a verified photograph
    # could be sourced. Once we have the real thing, it replaces the drawing
    # outright rather than sitting alongside it.
    page = page[:schematic.start()] + figure + page[schematic.end():]
    with open(path, "w", encoding="utf-8") as handle:
        handle.write(page)
    return "ok"


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--limit", type=int, default=0,
                        help="stop after this many records")
    parser.add_argument("--dry-run", action="store_true",
                        help="report what would happen, download nothing")
    args = parser.parse_args()

    if not os.path.exists("style.css"):
        sys.exit("run this from the repo root")
    if not os.path.exists(MATCHES):
        sys.exit("no %s yet - run scripts/photos.py first" % MATCHES)

    matches = json.load(open(MATCHES, encoding="utf-8"))
    counts = {}
    done = 0

    for path in sorted(matches):
        if args.limit and done >= args.limit:
            break
        if not os.path.exists(path):
            counts["record has gone"] = counts.get("record has gone", 0) + 1
            continue
        result = apply_one(path, matches[path], args.dry_run)
        counts[result] = counts.get(result, 0) + 1
        if result == "ok":
            done += 1
            if not args.dry_run:
                time.sleep(0.25)

    print("%d matches considered" % len(matches))
    for reason in sorted(counts, key=lambda r: -counts[r]):
        print("  %-32s %d" % (reason, counts[reason]))
    if not args.dry_run and counts.get("ok"):
        print("\nnow run scripts/images.py, then scripts/build.py, then scripts/check.py")


if __name__ == "__main__":
    main()
