# Everyday essentials in stocked default maps

Added 64 local photos, bringing the catalog to 960 pictures for 1,496 entries in
131 categories. Sixteen more departments now have a photo for every existing
product: household, stationery, souvenirs, checkout items, coffee-station goods,
pantry, books, electronics, home design, sports, hardware, music, garden supplies,
kitchen tools, laundry care and flowers. Their matching default maps inherit the
photos without changing product names, prices or SKU identities.

Integrated main through 67f64eba and the completed operator change e98e7204:
built-in model price fallback, shared shelf stock and checkout lines, and all 82
format descriptions in six languages. Custom descriptions and edited floor names
remain unchanged. New translated floor names avoid repeating the floor number.
Previously integrated catalog, model-recovery and localization fixes were retained.

Boundary review reproduced two upstream shared-stock issues: negative or oversized
per-product stock overrides were accepted, and products opening with zero stock
were missing from the stockout count and empty-duration total. Overrides now accept
0–10,000 units per shelf level; zero stock is counted from opening on each day.
Tests cover invalid values, two days, scheduled/disabled refilling, replacement
purchases and the maximum override across multiple shelf levels.

Validation on 2026-10-22:

- Focused stock/recovery/price checks: 43 passed in 7.74 seconds.
- Focused backend: 6,784 passed in 394.10 seconds, including 48 additional
  complete-department/map/currency cases, all-map catalog coverage, image/chart
  APIs, starter selection, exclusions, limits, saved templates and SKU compatibility.
- Strict backend types: zero errors; application boot passed.
- Full backend: 23,045 passed and one skipped in 1,122.86 seconds.
- Full frontend: 4,328 passed in 252 files in 248.72 seconds. Build passed in
  24.14 seconds; lint retained 19 warnings and zero errors.
- Browser automatic music-store creation passed with music and electronics
  departments. All 64 actual image endpoints and four galleries were inspected.
  The VLM grid displayed photos, names and prices; realistic rendering loaded four
  images without page errors.
- Browser default garden-center creation used the stocked format without a
  configured model. Saved racks exactly matched the preview including photos.
  The flower VLM grid displayed photos and readable names/prices; realistic
  rendering loaded 39 images without page errors. Both views were inspected.
- All six languages passed mobile (390 px) and desktop (1,280 px) checks for
  translated format descriptions, independent floor previews, saved floor names,
  reserved areas and localized SVG downloads. Saved racks exactly matched the
  preview including photos; the source layout remained unchanged. Korean mobile
  descriptions and French desktop floor review were visually inspected.
- Shared-stock controls passed both viewport sizes in all six languages, including
  invalid stock/patience values, blank refill/counter options and off/on state
  preservation. No simulation was started. Korean mobile and French desktop
  controls were visually inspected.
- All 60 original image atlases are included in the wheel, verified byte for byte.

Browser product-model availability/replies and persona generation used controlled
fixtures in disposable storage. No live provider completion, local-model download
or paid simulation was invoked.
