#!/usr/bin/env python3
"""Repair the archive's dead source links using the Wayback Machine.

    python3 scripts/links_repair.py --dry-run
    python3 scripts/links_repair.py

scripts/links.py finds the dead citations and writes hardware-archives/links.json.
This script tries to rescue them.

A manufacturer taking down a product page does not make the page wrong, it just
makes it unreachable. The Internet Archive usually has a copy from when it was
live, and a citation that points at a dated snapshot is arguably better than one
pointing at a live page that can change underneath it.

So for each dead URL:

  1. Re-check it. A timeout during a bulk scan is not proof of death, and it
     would be careless to rewrite a working link because a server was busy.
  2. Ask the Wayback Machine for the closest snapshot.
  3. If there is one, point the citation at it and mark the citation so a
     reader knows they are looking at an archived copy rather than a live page.

Links with no snapshot are left alone and listed at the end. Those need a human
to find a replacement source, and the script will not invent one.
"""

import argparse
import json
import os
import re
import ssl
import sys
import time
import urllib.error
import urllib.parse
import urllib.request

ROOT = "hardware-archives"
REPORT = os.path.join(ROOT, "links.json")
UA = ("Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) "
      "Chrome/124.0 Safari/537.36")
AVAILABILITY = "https://archive.org/wayback/available?url=%s"


def context():
    ctx = ssl.create_default_context()
    ctx.check_hostname = False
    ctx.verify_mode = ssl.CERT_NONE
    return ctx


def still_dead(url):
    """True only if the URL fails a second, patient check."""
    for method in ("HEAD", "GET"):
        try:
            request = urllib.request.Request(
                url, headers={"User-Agent": UA}, method=method)
            with urllib.request.urlopen(request, timeout=40, context=context()) as response:
                return not (200 <= response.status < 400)
        except urllib.error.HTTPError as err:
            if method == "HEAD" and err.code in (400, 405, 501):
                continue
            # A server that refuses us is not a dead page.
            return err.code not in (401, 403, 429, 503)
        except Exception:
            continue
    return True


def snapshot(url):
    """Closest Wayback snapshot URL, or None."""
    query = AVAILABILITY % urllib.parse.quote(url, safe="")
    for attempt in range(3):
        try:
            request = urllib.request.Request(query, headers={"User-Agent": UA})
            with urllib.request.urlopen(request, timeout=40, context=context()) as response:
                data = json.load(response)
            closest = data.get("archived_snapshots", {}).get("closest") or {}
            if closest.get("available") and closest.get("url"):
                # The API hands back http:// more often than not.
                return closest["url"].replace("http://web.archive.org",
                                              "https://web.archive.org")
            return None
        except Exception:
            time.sleep(2 ** attempt)
    return None


def rewrite(path, old, new):
    """Point one citation at its snapshot and say so in the note beside it."""
    with open(path, encoding="utf-8") as handle:
        page = handle.read()
    if old not in page:
        return False
    page = page.replace('href="%s"' % old, 'href="%s"' % new)

    # Mark the list item so the change is visible on the page, not just in git.
    item = re.search(
        r'(<li>(?:(?!</li>).)*?href="%s".*?)(</li>)' % re.escape(new),
        page, re.S)
    if item and "ARCHIVED COPY" not in item.group(1):
        note = (' <small>Original page is gone; this is the Internet Archive\u2019s '
                'copy.</small>')
        page = page[:item.end(1)] + note + page[item.end(1):]

    with open(path, "w", encoding="utf-8") as handle:
        handle.write(page)
    return True


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--limit", type=int, default=0)
    args = parser.parse_args()

    if not os.path.exists("style.css"):
        sys.exit("run this from the repo root")
    if not os.path.exists(REPORT):
        sys.exit("no %s yet - run scripts/links.py first" % REPORT)

    report = json.load(open(REPORT, encoding="utf-8"))
    dead = report.get("dead", {})
    cited_by = report.get("cited_by", {})
    print("%d dead links to try" % len(dead))

    revived = recovered = no_copy = alive_after_all = 0
    stranded = []

    for index, url in enumerate(sorted(dead), 1):
        if args.limit and recovered + no_copy + alive_after_all >= args.limit:
            break
        if not still_dead(url):
            alive_after_all += 1
            continue
        replacement = snapshot(url)
        if not replacement:
            no_copy += 1
            stranded.append(url)
            continue
        recovered += 1
        if not args.dry_run:
            for path in cited_by.get(url, []):
                if os.path.exists(path) and rewrite(path, url, replacement):
                    revived += 1
        if index % 25 == 0:
            print("  %d/%d" % (index, len(dead)), flush=True)
        time.sleep(0.2)

    print("\n  alive on a second look   %d" % alive_after_all)
    print("  snapshot found           %d" % recovered)
    print("  no snapshot anywhere     %d" % no_copy)
    if not args.dry_run:
        print("  citations rewritten      %d" % revived)
    if stranded:
        print("\nthese need a replacement source picked by hand:")
        for url in stranded[:40]:
            print("  %s" % url)
        if len(stranded) > 40:
            print("  ...and %d more" % (len(stranded) - 40))


if __name__ == "__main__":
    main()
