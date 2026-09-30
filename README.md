# Alien Cultist Labs

Source for [windows95br0.github.io](https://windows95br0.github.io) — the site for Alien Cultist Labs, a media preservation, repair, and hardware recovery shop in Galt, California.

`aliencultist.com` forwards to the GitHub Pages URL, which is the canonical home of the content.

## How it's built

Static HTML, CSS, and vanilla client-side JavaScript. **No build step and no dependencies** — GitHub Pages serves the files exactly as they are committed, so you can edit any page directly and push.

## Layout

| Path | What it is |
| --- | --- |
| `index.html` | Home page: services, about, contact |
| `shopwithus.html` | Build portfolio and buyer reviews |
| `dedicatedservers.html` | Game servers (placeholder) |
| `xrayarchives.html` | X-Ray Archives (placeholder) |
| `Maint.html` | Maintenance page, not linked from the site |
| `404.html` | Served by GitHub Pages for unknown URLs |
| `style.css` | Shared stylesheet and design tokens for every page |
| `scripts/site.js` | Shared behaviour for every page |
| `hardware-archives/` | ~4,200 pages of component reference records |
| `area-42/` | 668 source-led dossier pages |
| `assets/` | Images, logos, favicon, and social share cards |
| `sitemap.xml`, `robots.txt` | Generated for search engines |

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

Regenerate the sitemap so search engines see the change. It lists every page except `404.html` and `Maint.html`, and takes each page's `lastmod` from its most recent git commit.

## Images

Keep source images at a sensible size before committing — roughly 1600px on the longest edge is plenty for this layout. Oversized photos are the easiest way to make the site slow.

Social share cards live in `assets/images/og-*.jpg` at 1200×630, one per section palette.
