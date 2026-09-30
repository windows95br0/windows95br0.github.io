#!/usr/bin/env python3
"""Check every source link in the hardware archive and report the dead ones.

    python3 scripts/links.py            # check everything, write links.json
    python3 scripts/links.py --sample 200

Each part record cites its sources. Over time some of those pages move or go
away, and a citation that 404s is worse than no citation at all, because it
looks like it was checked.

Plenty of documentation hosts answer an automated request with 403 while
serving the same page perfectly well to a browser. Those are reported
separately as "blocked", not as dead, because we cannot tell from here and
guessing would throw away good links.

The script only reports. Nothing is edited automatically; a replacement source
is a judgement call.
"""

import argparse
import collections
import concurrent.futures
import glob
import json
import os
import re
import ssl
import sys
import urllib.error
import urllib.request

ROOT = "hardware-archives"
OUT = os.path.join(ROOT, "links.json")
UA = ("Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) "
      "Chrome/124.0 Safari/537.36")

# Read as "the server answered, it just will not answer us".
BLOCKED = {401, 403, 429, 503}


def collect():
    """Every source URL in the archive, with the pages that cite it."""
    citations = collections.defaultdict(set)
    pattern = re.compile(r'<ol class="record-sources">(.*?)</ol>', re.S)
    link = re.compile(r'href="(https?://[^"]+)"')
    for path in glob.glob(os.path.join(ROOT, "**", "index.html"), recursive=True):
        with open(path, encoding="utf-8") as handle:
            page = handle.read()
        for block in pattern.findall(page):
            for url in link.findall(block):
                citations[url].add(path)
    return citations


def probe(url):
    """(url, status) where status is an HTTP code or a short failure word."""
    context = ssl.create_default_context()
    context.check_hostname = False
    context.verify_mode = ssl.CERT_NONE
    headers = {
        "User-Agent": UA,
        "Accept": "text/html,application/xhtml+xml,*/*;q=0.8",
        "Accept-Language": "en-US,en;q=0.9",
    }
    # HEAD is cheaper, but a fair number of hosts mishandle it, so fall back.
    for method in ("HEAD", "GET"):
        try:
            request = urllib.request.Request(url, headers=headers, method=method)
            with urllib.request.urlopen(request, timeout=25, context=context) as response:
                return url, response.status
        except urllib.error.HTTPError as err:
            if method == "HEAD" and err.code in (400, 405, 501):
                continue
            return url, err.code
        except urllib.error.URLError as err:
            return url, "unreachable: %s" % (err.reason,)
        except Exception as err:
            return url, "failed: %s" % (type(err).__name__,)
    return url, "failed"


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--sample", type=int, default=0,
                        help="check only this many URLs, evenly spread")
    parser.add_argument("--workers", type=int, default=16)
    args = parser.parse_args()

    if not os.path.exists("style.css"):
        sys.exit("run this from the repo root")

    citations = collect()
    urls = sorted(citations)
    print("%d source links, %d unique URLs" % (
        sum(len(p) for p in citations.values()), len(urls)))

    if args.sample and args.sample < len(urls):
        step = len(urls) / args.sample
        urls = [urls[int(i * step)] for i in range(args.sample)]
        print("checking a spread sample of %d" % len(urls))

    results = {}
    done = 0
    with concurrent.futures.ThreadPoolExecutor(max_workers=args.workers) as pool:
        for url, status in pool.map(probe, urls):
            results[url] = status
            done += 1
            if done % 200 == 0:
                print("  %d/%d" % (done, len(urls)), flush=True)

    ok, blocked, dead = [], [], []
    for url, status in results.items():
        if isinstance(status, int) and 200 <= status < 400:
            ok.append(url)
        elif isinstance(status, int) and status in BLOCKED:
            blocked.append(url)
        else:
            dead.append(url)

    report = {
        "checked": len(results),
        "ok": len(ok),
        "blocked": sorted(blocked),
        "dead": {u: results[u] for u in sorted(dead)},
        "cited_by": {u: sorted(citations[u]) for u in sorted(dead)},
    }
    with open(OUT, "w", encoding="utf-8") as handle:
        json.dump(report, handle, indent=1, sort_keys=True)

    print("\n  reachable   %d" % len(ok))
    print("  blocked     %d  (server refused us, probably fine in a browser)" % len(blocked))
    print("  dead        %d" % len(dead))
    if dead:
        pages = len({p for u in dead for p in citations[u]})
        print("  ...cited by %d pages" % pages)
        print("\nfull report in %s" % OUT)
        for url in sorted(dead)[:15]:
            print("  %-6s %s" % (results[url], url))


if __name__ == "__main__":
    main()
