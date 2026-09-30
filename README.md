# Alien Cultist Labs

Source for [windows95br0.github.io](https://windows95br0.github.io) — the site for Alien Cultist Labs, a media preservation, repair, and hardware recovery shop in Galt, California.

`aliencultist.com` forwards to the GitHub Pages URL, which is the canonical home of the content.

## How it's built

Static HTML, CSS, and vanilla client-side JavaScript. **No build step and no dependencies** — GitHub Pages serves the files exactly as they are committed, so you can edit any page directly and push.

## Layout

| Path | What it is |
| --- | --- |
| `index.html` | Home page: services, about, contact |
| `pricing.html` | Rate card and common questions |
| `search.html` | Searches every page on the site |
| `shopwithus.html` | Build portfolio and buyer reviews |
| `dedicatedservers.html` | Game servers (placeholder) |
| `xrayarchives.html` | X-Ray Archives (placeholder) |
| `Maint.html` | Maintenance page, not linked from the site |
| `404.html` | Served by GitHub Pages for unknown URLs |
| `style.css` | Shared stylesheet and design tokens for every page |
| `scripts/site.js` | Shared behaviour for every page |
| `scripts/search.js` | Search page only |
| `scripts/build.py` | Regenerates the files below |
| `scripts/images.py` | Makes WebP copies and wraps images in `<picture>` |
| `scripts/check.py` | Finds pages that have drifted out of sync |
| `hardware-archives/` | ~4,200 pages of component reference records |
| `area-42/` | 668 source-led dossier pages |
| `assets/` | Images, logos, favicon, and social share cards |
| `sitemap.xml`, `robots.txt` | Generated for search engines |
| `search-index.json` | Generated; powers `search.html` |

Both archive sections load `style.css` first and then their own `archive.css`, which overrides the colour tokens to give each section its own palette.

## Design tokens

Colours and fonts are CSS custom properties at the top of `style.css`. Change them there rather than in individual rules:

```css
:root {
  --ink: #040912;     /* page background */
  --paper: #ebfeff;   /* body text */
  --cyan: #7afaff;    /* primary accent */
  --pink: #ff59f0;    /* secondary accent */
  --yellow: #ffe66d;  /* highlight */
}
```

Sections re-declare these on a body class (`.shop-page`, `.hardware-page`, `.area42-page`, `.coming-soon-page`) to reskin a whole area without touching its markup.

## Shared JavaScript

`scripts/site.js` runs on every page and adds, where relevant:

- **Archive filter** — a live search box on any index page with 8 or more cards
- **Mobile menu toggle** — collapses the nav below 800px
- **Back-to-top button** — appears after scrolling 600px
- **Skip-to-content link** — for keyboard and screen-reader users

Everything degrades gracefully: if the script fails to load, the pages still work, they just lose these extras.

## Working on the site

Preview locally with any static server:

```bash
python3 -m http.server 8000
```

Then open <http://localhost:8000>.

### Adding a page

Copy the `<head>`, header, and footer from an existing page in the same section so the navigation, share tags, and styles stay consistent. Each page needs:

- a unique `<title>` and `<meta name="description">`
- `<link rel="canonical">` and the `og:` / `twitter:` tags, with paths relative to the page's depth
- `<script src="…/scripts/site.js" defer>` before `</body>`
- `loading="lazy"`, `decoding="async"`, and `width`/`height` on images below the fold

### After adding or removing pages

Regenerate the derived files:

```bash
python3 scripts/build.py
```

This rewrites `sitemap.xml` and `search-index.json` from the pages on disk, taking each page's `lastmod` from its most recent git commit and its search title from its `<title>` tag. `404.html`, `Maint.html`, and `search.html` are deliberately left out of both.

Commit the regenerated files along with your page changes — GitHub Pages cannot run this script for you.

### Before you commit

```bash
python3 scripts/check.py
```

Every header, nav, and meta tag on this site is hand-copied across roughly 4,900 files. There is no template to change, so a sitewide edit that misses a few hundred pages looks exactly like one that worked. This script is what tells the difference.

It reads every page and reports:

- internal links that point at files which do not exist
- pages that can no longer reach the home page or the search page
- missing, empty, or duplicated `description`, `canonical`, `og:`, and `twitter:` tags
- JSON-LD blocks that do not parse
- images that are missing, have no `alt`, or declare a size they are not
- `<picture>` tags that are unbalanced or point at a missing WebP
- entries in `search-index.json` whose page has since been deleted or renamed

It exits non-zero when it finds anything, and prints `all clear` when it doesn't. Run it after any bulk edit — that is exactly when things break quietly.

## Search

`search.html` downloads `search-index.json` once, on demand, and filters it in the browser. Nothing is sent anywhere.

The index stores directory names once in a lookup table and references them by position, which keeps roughly 4,900 entries down to about 350KB — around 96KB gzipped, which is what actually travels.

Because the index is built from `<title>` tags, a page with a vague title is hard to find. Titles ending in a section name (`// Hardware Archives`, `// Area 42`) have that part stripped automatically, since results already show the section.

## Images

Keep source images at a sensible size before committing — roughly 1600px on the longest edge is plenty for this layout. Oversized photos are the easiest way to make the site slow.

After adding or replacing any JPG, PNG, or GIF, run:

```bash
python3 scripts/images.py
```

This writes a `.webp` next to each image and wraps the `<img>` tag in a `<picture>`, so modern browsers get the smaller file while the original stays as the fallback. Across the site that cuts 19.3MB of photos down to 11.2MB.

Two things worth knowing:

- A WebP is only kept when it saves at least 5%. Grainy scans and historical photographs often compress better as JPEG, so about a quarter of the images are deliberately left alone.
- `style.css` sets `picture { display: contents; }`. Without it the wrapper becomes an inline box between the image and its container, which breaks the sizing rules that target `.service-image img` and friends. Don't remove it.

Re-running the script is safe; it only touches images that changed and tags that aren't wrapped yet.

Social share cards live in `assets/images/og-*.jpg` at 1200×630, one per section palette. They're referenced directly in meta tags, so they stay JPEG.
