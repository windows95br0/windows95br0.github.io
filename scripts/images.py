#!/usr/bin/env python3
"""Generate WebP copies of site images and wrap the <img> tags in <picture>.

Run from the repo root after adding or replacing any JPG/PNG/GIF:

    python3 scripts/images.py

Every original stays on disk and stays as the <img src>, so browsers without
WebP support keep working. A WebP is only kept when it saves at least 5%,
which is why a handful of grainy historical photos are still plain JPEG.

The script is idempotent: running it twice makes no further changes.
"""

import glob
import os
import re
import subprocess
import sys

QUALITY = "88"  # measured at ~40 dB PSNR, i.e. visually identical
MIN_SAVING = 0.95  # keep the WebP only if it is at least 5% smaller
RASTER = ("jpg", "jpeg", "png", "gif")

IMG_RE = re.compile(r"<img[^>]*?>", re.I)
SRC_RE = re.compile(r'src="([^"]+)"', re.I)


def referenced_images():
    """Every raster image that some page actually points at, as a repo path."""
    found = set()
    for page in glob.glob("**/*.html", recursive=True):
        with open(page, encoding="utf-8") as fh:
            html = fh.read()
        for match in IMG_RE.finditer(html):
            src = SRC_RE.search(match.group(0))
            if not src or src.group(1).lower().rsplit(".", 1)[-1] not in RASTER:
                continue
            path = os.path.normpath(os.path.join(os.path.dirname(page), src.group(1)))
            if os.path.exists(path):
                found.add(path)
    return found


def convert(images):
    made = skipped = 0
    before = after = 0
    for path in sorted(images):
        webp = path.rsplit(".", 1)[0] + ".webp"
        if os.path.exists(webp) and os.path.getmtime(webp) >= os.path.getmtime(path):
            before += os.path.getsize(path)
            after += os.path.getsize(webp)
            made += 1
            continue
        # [0] takes the first frame, which keeps single-frame GIFs working.
        result = subprocess.run(
            ["magick", path + "[0]", "-quality", QUALITY,
             "-define", "webp:method=6", webp],
            capture_output=True, text=True,
        )
        if result.returncode != 0 or not os.path.exists(webp):
            print("  could not convert", path, file=sys.stderr)
            skipped += 1
            continue
        original, converted = os.path.getsize(path), os.path.getsize(webp)
        if converted >= original * MIN_SAVING:
            os.remove(webp)  # JPEG already wins on this one
            skipped += 1
            continue
        before += original
        after += converted
        made += 1
    return made, skipped, before, after


def already_wrapped(html, index):
    """True when the <img> at this offset already sits inside a <picture>."""
    return html.rfind("<picture", 0, index) > html.rfind("</picture>", 0, index)


def wrap_pages():
    pages = wrapped = 0
    for page in sorted(glob.glob("**/*.html", recursive=True)):
        with open(page, encoding="utf-8") as fh:
            html = fh.read()
        parts, cursor, count = [], 0, 0
        for match in IMG_RE.finditer(html):
            tag = match.group(0)
            src = SRC_RE.search(tag)
            if not src or src.group(1).lower().rsplit(".", 1)[-1] not in RASTER:
                continue
            if already_wrapped(html, match.start()):
                continue
            webp = src.group(1).rsplit(".", 1)[0] + ".webp"
            if not os.path.exists(
                os.path.normpath(os.path.join(os.path.dirname(page), webp))
            ):
                continue
            parts.append(html[cursor:match.start()])
            parts.append(
                '<picture><source srcset="%s" type="image/webp">%s</picture>'
                % (webp, tag)
            )
            cursor = match.end()
            count += 1
        if count:
            parts.append(html[cursor:])
            with open(page, "w", encoding="utf-8") as fh:
                fh.write("".join(parts))
            pages += 1
            wrapped += count
    return pages, wrapped


def main():
    if not os.path.exists("style.css"):
        sys.exit("run this from the repo root")
    images = referenced_images()
    made, skipped, before, after = convert(images)
    saved = (before - after) * 100 // before if before else 0
    print("images referenced   %d" % len(images))
    print("webp kept           %d  (%.1f MB -> %.1f MB, %d%% smaller)"
          % (made, before / 1048576, after / 1048576, saved))
    print("left as-is          %d  (webp was no smaller)" % skipped)
    pages, wrapped = wrap_pages()
    print("newly wrapped       %d <img> tags across %d pages" % (wrapped, pages))


if __name__ == "__main__":
    main()
