# Figure and film sources

Everything in `../twinstore/` that is drawn rather than captured is generated from the HTML here.

| File | Output |
| :-- | :-- |
| `architecture.html`, `vision-shopper.html`, `shelf-lab.html`, `validation.html`, `launcher.html` | `../twinstore/<name>.png` (white, 3200 px wide) |
| `promo.html` | `../twinstore/twinstore-promo.mp4`, `twinstore-teaser.webp`, `twinstore-promo-poster.jpg` |
| `kit.css`, `kit.js`, `icons.js` | the shared look: cards, zones, chips, aurora connectors (`data-wires` on `<body>`), line icons |

```bash
node .github/assets/src/render.mjs                 # all figures (or name pages: render.mjs shelf-lab.html)
node .github/assets/src/render-video.mjs           # the film; --stills 3,12,20 for single frames
open .github/assets/src/promo.html?play            # watch the film in a browser; ?t=12 freezes a moment
```

Needs Playwright with Chromium, ffmpeg, and `frontend/node_modules` (the pages load Geist, Geist Mono and Instrument
Serif from there). Screenshots in `../twinstore/screens/` and shelf images in `../twinstore/media/` are captured from
the running app and the Shelf Lab engine; the numbers in `validation.html` come from `research/validation/README.md`.
