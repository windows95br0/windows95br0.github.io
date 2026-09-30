#!/usr/bin/env python3
"""Regenerate the files that are derived from the site's pages.

Run this after adding, renaming, or removing any HTML page:

    python3 scripts/build.py

It writes sitemap.xml (for search engines) and search-index.json (for the
site's own search page). Both are committed, because GitHub Pages serves
this repository exactly as-is and cannot run a build step.
"""

import datetime
import glob
import html
import json
import os
import re
import subprocess
import sys
import xml.sax.saxutils as sx

SITE = 'https://windows95br0.github.io'

# Pages that should not be advertised to search engines or the site search.
EXCLUDE = {'404.html', 'Maint.html', 'search.html'}

# Trailing branding removed from titles, longest first so the more specific
# suffixes win.
TITLE_SUFFIXES = (
    '| Area 42 Dossier', '// Alien Cultist Labs', '// Hardware Archives',
    '// Area 42', '| Alien Cultist Labs',
)

SECTIONS = ('Hardware Archives', 'Area 42', 'Alien Cultist Labs')


def repo_root():
    return os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def page_paths():
    return sorted(p.replace(os.sep, '/') for p in glob.glob('**/*.html', recursive=True))


def canonical_path(page):
    """The URL GitHub Pages serves for a file, relative to the site root."""
    if page == 'index.html':
        return '/'
    if page.endswith('/index.html'):
        return '/' + page[:-len('index.html')]
    return '/' + page


def read_title(page):
    with open(page, encoding='utf-8') as fh:
        head = fh.read(4000)
    match = re.search(r'<title>(.*?)</title>', head, re.S)
    if not match:
        return ''
    title = html.unescape(re.sub(r'\s+', ' ', match.group(1))).strip()
    # Titles end with branding or the section name, both of which the search
    # results already show from the entry's own section and category.
    title = title.split(' // ')[0].strip()
    for suffix in TITLE_SUFFIXES:
        plain = html.unescape(suffix)
        if title.endswith(plain):
            title = title[:-len(plain)].rstrip(' /|').strip()
            break
    return title


def prefix_label(prefix):
    """A readable category name for a directory of archive pages."""
    parts = [p for p in prefix.split('/') if p and p != 'components' and p != 'dossiers']
    if not parts:
        return ''
    if parts[0] in ('hardware-archives', 'area-42'):
        parts = parts[1:]
    if not parts:
        return ''
    return parts[-1].replace('-', ' ').title()


def commit_dates():
    """Map every tracked file to the date of the commit that last touched it."""
    try:
        log = subprocess.run(
            ['git', 'log', '--name-only', '--pretty=format:%cs', '--'],
            capture_output=True, text=True, timeout=600, check=True).stdout
    except (subprocess.SubprocessError, OSError):
        return {}
    dates, current = {}, None
    for line in log.splitlines():
        line = line.strip()
        if not line:
            continue
        if len(line) == 10 and line[4] == '-' and line[7] == '-':
            current = line
        elif current and line not in dates:
            dates[line] = current
    return dates


def priority(page):
    if page == 'index.html':
        return '1.0', 'weekly'
    if page == 'pricing.html':
        return '0.9', 'monthly'
    if page.endswith('/index.html'):
        depth = page.count('/')
        return ('0.8' if depth == 1 else '0.6' if depth == 2 else '0.5',
                'weekly' if depth == 1 else 'monthly')
    return ('0.7', 'monthly') if '/' not in page else ('0.4', 'monthly')


def write_sitemap(pages, dates):
    today = datetime.date.today().isoformat()
    lines = ['<?xml version="1.0" encoding="UTF-8"?>',
             '<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">']
    for page in pages:
        pri, freq = priority(page)
        lines.append(
            '<url><loc>%s</loc><lastmod>%s</lastmod><changefreq>%s</changefreq>'
            '<priority>%s</priority></url>'
            % (sx.escape(SITE + canonical_path(page)), dates.get(page, today), freq, pri))
    lines.append('</urlset>')
    with open('sitemap.xml', 'w', encoding='utf-8') as fh:
        fh.write('\n'.join(lines) + '\n')
    return len(pages)


def section_of(page):
    if page.startswith('hardware-archives/'):
        return 0
    if page.startswith('area-42/'):
        return 1
    return 2


def write_search_index(pages):
    """Write a compact index the search page can download in one request.

    Directory names repeat heavily across the archives, so they are stored
    once in a lookup table and each entry references one by position. Entries
    record the URL the site actually serves, which for most archive pages is
    a directory rather than a .html file.
    """
    prefixes, prefix_ids, docs = [], {}, []
    for page in pages:
        url = canonical_path(page).lstrip('/')
        is_dir = url.endswith('/') or url == ''
        trimmed = url[:-1] if url.endswith('/') else url
        directory, _, name = trimmed.rpartition('/')
        directory = directory + '/' if directory else ''
        if not is_dir and name.endswith('.html'):
            name = name[:-len('.html')]
        if directory not in prefix_ids:
            prefix_ids[directory] = len(prefixes)
            prefixes.append(directory)
        title = read_title(page)
        if not title:
            continue
        docs.append([prefix_ids[directory], name, title,
                     section_of(page), 1 if is_dir else 0])

    index = {'v': 1, 'sections': list(SECTIONS), 'prefixes': prefixes,
             'labels': [prefix_label(p) for p in prefixes], 'docs': docs}
    with open('search-index.json', 'w', encoding='utf-8') as fh:
        json.dump(index, fh, ensure_ascii=False, separators=(',', ':'))
    return len(docs)


def main():
    os.chdir(repo_root())
    pages = [p for p in page_paths() if p not in EXCLUDE]
    if not pages:
        sys.exit('No HTML pages found - run this from inside the repository.')

    urls = write_sitemap(pages, commit_dates())
    entries = write_search_index(pages)

    size = os.path.getsize('search-index.json') / 1024
    print('sitemap.xml        %d urls' % urls)
    print('search-index.json  %d entries (%.0f KB)' % (entries, size))


if __name__ == '__main__':
    main()
