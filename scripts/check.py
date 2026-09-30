#!/usr/bin/env python3
"""Check every page for the things that quietly drift out of sync.

    python3 scripts/check.py

There is no build step for the pages themselves, so every header, nav, and
meta tag is hand-copied across ~4,900 files. That works right up until one
sitewide edit misses a few hundred pages, and nothing tells you. This script
is the thing that tells you.

Exits non-zero when it finds a problem, so it can gate a commit.
"""

import glob
import json
import os
import re
import subprocess
import sys
from collections import defaultdict

SKIP_META = {"404.html", "Maint.html"}
NOINDEX = {"search.html"}
RASTER = ("jpg", "jpeg", "png", "gif")
LINK_SCHEMES = re.compile(r"^(https?:|mailto:|tel:|sms:|javascript:|data:|#|//)", re.I)

IMG_RE = re.compile(r"<img[^>]*?>", re.I)
ATTR = lambda tag, name: (
    m.group(1) if (m := re.search(name + r'="([^"]*)"', tag, re.I)) else None
)


def rel(path):
    return os.path.relpath(path).replace(os.sep, "/")


def resolve(page, href):
    """Where an href on a given page actually lands, as a repo-relative path."""
    target = href.split("#")[0].split("?")[0]
    if not target:
        return None
    path = os.path.normpath(os.path.join(os.path.dirname(page), target))
    if target.endswith("/") or os.path.isdir(path):
        path = os.path.join(path, "index.html")
    return rel(path)


def image_size(path):
    out = subprocess.run(
        ["magick", "identify", "-format", "%w %h", path + "[0]"],
        capture_output=True, text=True,
    ).stdout.split()
    return (out[0], out[1]) if len(out) == 2 else None


def main():
    if not os.path.exists("style.css"):
        sys.exit("run this from the repo root")

    pages = sorted(rel(p) for p in glob.glob("**/*.html", recursive=True))
    on_disk = {rel(p) for p in glob.glob("**/*", recursive=True) if os.path.isfile(p)}
    problems = defaultdict(list)
    checked_sizes = {}

    for page in pages:
        with open(page, encoding="utf-8") as fh:
            html = fh.read()
        name = os.path.basename(page)

        # Every internal link has to land on a file that exists.
        targets = set()
        for href in re.findall(r'href="([^"]+)"', html):
            if LINK_SCHEMES.match(href):
                continue
            landing = resolve(page, href)
            if landing is None:
                continue
            targets.add(landing)
            if landing not in on_disk:
                problems["broken link"].append("%s -> %s" % (page, href))

        # Nothing should be a dead end. Home and search must stay reachable.
        if name not in SKIP_META:
            if "index.html" not in targets and page != "index.html":
                problems["no link home"].append(page)
            if "search.html" not in targets and page not in NOINDEX:
                problems["no link to search"].append(page)

        # Metadata that search engines and link previews depend on.
        if name not in SKIP_META:
            for tag, pattern in (
                ("description", r'<meta[^>]+name="description"[^>]+content="([^"]*)"'),
                ("canonical", r'<link[^>]+rel="canonical"[^>]+href="([^"]*)"'),
                ("og:title", r'<meta[^>]+property="og:title"[^>]+content="([^"]*)"'),
                ("og:image", r'<meta[^>]+property="og:image"[^>]+content="([^"]*)"'),
                ("twitter:card", r'<meta[^>]+name="twitter:card"[^>]+content="([^"]*)"'),
            ):
                found = re.findall(pattern, html, re.I)
                if page in NOINDEX and tag == "canonical":
                    continue
                if not found:
                    problems["missing " + tag].append(page)
                elif len(found) > 1:
                    problems["duplicate " + tag].append(page)
                elif not found[0].strip():
                    problems["empty " + tag].append(page)

        # Structured data has to parse or it is worse than not being there.
        for block in re.findall(
            r'<script[^>]*application/ld\+json[^>]*>(.*?)</script>', html, re.S | re.I
        ):
            try:
                json.loads(block)
            except ValueError as err:
                problems["invalid JSON-LD"].append("%s: %s" % (page, err))

        # <picture> must be balanced, and its sources must exist.
        if html.count("<picture") != html.count("</picture>"):
            problems["unbalanced <picture>"].append(page)
        for srcset in re.findall(r'<source[^>]*srcset="([^"]+)"', html, re.I):
            if resolve(page, srcset) not in on_disk:
                problems["missing webp source"].append("%s -> %s" % (page, srcset))

        # Images: real file, alt text, honest width/height, WebP where useful.
        for tag in IMG_RE.findall(html):
            src = ATTR(tag, "src")
            if not src:
                problems["img without src"].append(page)
                continue
            landing = resolve(page, src)
            if landing not in on_disk:
                problems["missing image"].append("%s -> %s" % (page, src))
                continue
            if ATTR(tag, "alt") is None:
                problems["img without alt"].append("%s -> %s" % (page, src))
            ext = src.lower().rsplit(".", 1)[-1]
            if ext in RASTER:
                webp = resolve(page, src.rsplit(".", 1)[0] + ".webp")
                if webp in on_disk and "<picture" not in html:
                    problems["webp exists but img not wrapped"].append(
                        "%s -> %s" % (page, src)
                    )
                width, height = ATTR(tag, "width"), ATTR(tag, "height")
                if width and height and landing not in checked_sizes:
                    checked_sizes[landing] = image_size(landing)
                actual = checked_sizes.get(landing)
                if width and height and actual and (width, height) != actual:
                    problems["wrong img dimensions"].append(
                        "%s -> %s declared %sx%s actual %sx%s"
                        % (page, src, width, height, actual[0], actual[1])
                    )

    # Derived files must still match the pages on disk.
    for derived in ("sitemap.xml", "search-index.json"):
        if not os.path.exists(derived):
            problems["missing derived file"].append(derived + " (run scripts/build.py)")

    if os.path.exists("search-index.json"):
        with open("search-index.json", encoding="utf-8") as fh:
            index = json.load(fh)
        for prefix_idx, name, _title, _section, is_dir in index["docs"]:
            url = index["prefixes"][prefix_idx] + name + ("/index.html" if is_dir else ".html")
            if url.lstrip("/") not in on_disk:
                problems["stale search index"].append(url)

    print("checked %d pages\n" % len(pages))
    if not problems:
        print("all clear")
        return 0
    total = 0
    for kind in sorted(problems):
        items = problems[kind]
        total += len(items)
        print("%s (%d)" % (kind, len(items)))
        for item in items[:8]:
            print("   ", item)
        if len(items) > 8:
            print("    ... and %d more" % (len(items) - 8))
        print()
    print("%d problem(s)" % total)
    return 1


if __name__ == "__main__":
    sys.exit(main())
