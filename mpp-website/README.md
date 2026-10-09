# Mike's Pumpkin Patch

A responsive, rustic redesign using only HTML, CSS, and client-side JavaScript. No framework, build process, backend, or dependencies are required.

## Preview

Open `index.html` in a browser, or serve the directory locally:

```sh
python3 -m http.server 8000 --bind 127.0.0.1
```

Then visit `http://127.0.0.1:8000`.

## Publish

Upload `index.html`, `styles.css`, `script.js`, and the `assets` directory to any static web host. The current WordPress installation is not changed by this local redesign.

## Content and maintenance

- The owner confirmed that the patch is open for the 2026 season.
- Hours, admission prices, and current pumpkin prices are intentionally not invented. Visitors are directed to call for confirmed details. Update these in the “Plan your visit” section when available.
- Address, phone, email, activity information, driving directions, and field-trip information were taken from the existing Mike's Pumpkin Patch website. Confirm seasonal activity availability before publishing.
- The displayed photographs now come from the original website's media library and show the ranch itself, rather than stock scenes. They depict previous seasons; they do not promise a particular 2026 maze layout. Confirm photo permissions, including recognizable visitors, before publishing.
- New photo sources (all under `https://mikespumpkinpatch.com/wp-content/uploads/`): `pumpkins-scaled.jpg`, `pumpkins-and-kids-scaled.jpg`, `maze-1-scaled.jpg`, `maze-above.jpg`, `goats-scaled-e1759951443644.jpg`, `8-1.jpg`, and `pillow-bouncer.png`. Where available, the site's 1024-pixel variants are used to reduce download size.
- Gallery photos link directly to the local image for a larger view and work without JavaScript. A Google Maps link lets visitors browse additional photos there; third-party Maps photos are not downloaded or republished.
- The header and footer use the original Mike's Pumpkin Patch logo, unchanged. The favicon also comes from the existing site.
- Google Fonts provides optional Fraunces and DM Sans fonts. System serif and sans-serif fallbacks are supplied if fonts cannot load. All other assets are local.
- Field-trip and contact links open the visitor's email application. There is no simulated booking or contact submission, no payment processing, and no server-side form.
- The menu and activity filters use `script.js`. All activities, navigation links, and native FAQ disclosures remain available without JavaScript.
- The footer year updates automatically. The season announcement is intentionally maintained separately.

## Accessibility

Includes semantic sections, descriptive photo alternatives, a skip link, visible keyboard focus, native disclosure controls, accessible menu/filter states, and reduced-motion support.
