# Home and craft starter products

Added 96 products in eight categories: home linens, dinnerware, food storage,
pet grooming, hair accessories, woodcraft, ceramic craft and gift wrapping.
Added 32 photos for these categories and existing sports, pets, home and baby
products. The catalog now contains 1,400 products in 123 categories with 352
bundled photos, available to automatic selection and manual placement.

Integrated completed shelf-copy localization and stable neighborhood trip-order
changes from 299ee2b, retaining the newer 0.4.6 interface and 256-tile store limit.
Merged 0442888's run-history locks and written-customer panel preference.

Validation on 2026-10-22:

- Targeted backend: 2,791 passed in 141.20 seconds, covering all categories in
  USD/KRW/JPY, image grids, legacy-photo resolution, automatic selection, template
  placement, shelf reuse, neighborhood ordering and run-history locks.
- Strict backend types: zero errors; application boot passed.
- Full backend: 19,451 passed, one skipped in 1,045.48 seconds.
- Targeted frontend: 305 passed. Corrected imported test expectations for current
  server-provided English format names and the selected language's neighborhood label.
- Full frontend: 4,090 passed in 233 files; build passed in 22.34 seconds; lint
  retained 19 warnings and zero errors.
- Browser: a new store used automatic placement by default and contained all eight
  new categories. The actual shelf-preview API displayed photos, names, prices and
  numbered choices. Both new photo galleries and the VLM chart were visually inspected.
- Realistic rendering loaded 16 bundled photos without page errors; visually inspected.
- Six-language shelf-copy browser checks passed at 390 and 1280 px widths, with
  reachable save buttons, exact copied slots, unchanged source data and no page errors.
  The resize check now waits for pointer actionability before taking measurements.
- All 22 original atlases are present in the wheel. New product names and exact
  identities are distinct from existing products; 352 photo bindings verified.

Browser product-model/persona replies were controlled fixtures; shelf-copy checks
use actual storage and API calls. No live provider completion or paid simulation
was invoked.
