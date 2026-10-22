# Complete outdoor and craft photos in default maps

Added the remaining 64 photos for yoga and Pilates, running, fishing, leathercraft,
seed starting, plant propagation, candle care and camping repairs. Each of these
8 departments now has a photo for every product in its matching default maps.
The catalog contains 1,688 products, 147 categories and 1,152 local photos in
72 atlases. Existing product identities, prices and map geometry are preserved.

Integrated upstream finite backroom stock and daily delivery support. Boundary
checks found that a backroom starting at zero hid the entire shortage report.
The view now includes zero-stock backrooms, per-product limits and a configured
empty backroom with no shortfall. The configuration documentation no longer
claims that every shelf always opens full.

Validation on 2026-10-22:

- Eighteen reporting regressions across six languages failed before the fix and
  passed afterward. Seventy-two week-long inventory cases cover shelf quantities,
  zero/finite backrooms, per-product overrides, delivery on/off and refill timing;
  another case checks that two shelves draw from the same product stock pool.
- Shared-store engine, API, saved layout operations and comparison checks:
  184 passed in 25.82 seconds. The initial inventory test incorrectly expected
  shortages even when morning deliveries supplied enough stock; its assertion
  was corrected to cover that distinction.
- New image endpoints and manifest: 84 passed in 10.00 seconds. Fully pictured
  default departments across ten maps and three currencies: 30 passed in 0.77 seconds.
- Strict backend types: zero errors; application boot passed. Full backend: 24,597 passed and one skipped in 1,337.64 seconds.
- Focused UI and package checks: 170 passed in 9.38 seconds. Full frontend:
  4,394 passed across 256 files in 236.85 seconds. Build passed in 21.14 seconds;
  lint retained 19 warnings and zero errors.
- Four product browser checks passed: automatic sports-outlet selection and
  default art-and-craft stocking, preview matching the saved racks, both actual
  VLM image grids, all 64 new image endpoints and both 3D stores. The automatic
  store loaded eight photos; the default store loaded all 77. The 3D test now
  waits for every expected photo instead of assuming loading finishes in 1.5 seconds.
  All four endpoint galleries, both VLM grids and both 3D views were inspected.
- Actual zero-backroom reports, input limits, memory replay/planning/apply and
  saved layout settings passed in all six languages at 390 px and 1,280 px.
  Applied plans reproduced the daily outcome and both memory weeks exactly;
  saving and reopening retained zero-stock/backroom overrides, delivery off and
  hourly tills. Delayed/failed settings loads blocked execution and estimates,
  and retry restored the saved plan. No extra run was started and saved run
  output files stayed byte-identical. Korean mobile and French desktop shortage
  reports and the Spanish mobile weekly comparison were visually inspected.
  The backroom controls also passed all six languages at both widths; Korean
  mobile and French desktop controls were visually inspected.
- All 72 original atlases are included in the wheel, verified byte for byte.

Browser and API checks use disposable storage, controlled category/persona
fixtures and rule-based previews. No live model completion or paid simulation
is used. Generated product photographs are bundled as catalog assets.
