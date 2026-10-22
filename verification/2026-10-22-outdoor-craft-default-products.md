# Outdoor and craft products in default maps

Added 96 products across yoga and Pilates, running accessories, fishing tackle,
leathercraft, seed starting, plant propagation, candle care and camping repairs.
The catalog now includes 1,688 products in 147 categories and 1,088 photos in 68
atlases. Ten matching default maps stock the added departments, preserving their
existing products and geometry. Labels are provided in all six interface languages.

Integrated saved layout operations: copies retain stock/refill/till settings, and
runs, A/B experiments and optimization can use the layout's saved plan. The lab can
save a tested plan for the layout. Boundary tests reproduced three cases where a
run could start with default settings while the saved settings were still loading
or had failed to load. The launcher now waits for successful loading, prevents
editing the temporary defaults, and offers retry after an error. Zero-stock
product overrides and hourly till settings are carried into the run.

Validation on 2026-10-22:

- Layout operations, shared-store API and simulation checks: 100 passed in
  21.84 seconds.
- New map, currency, seed, small-map limit and exclusion checks: 120 passed
  in 1.20 seconds. New image endpoint checks: 46 passed in 5.26 seconds.
- Strict backend types: zero errors; application boot passed.
- Focused launcher, lab, model-selection, shelf-photo and A/B UI checks:
  195 passed in 14.08 seconds. The three new loading/retry regressions failed
  before the fix and passed afterward. Older launcher fixtures now provide the
  layout-settings response and wait for loading before expecting an enabled run.
- Frontend build passed in 20.84 seconds. Lint retained 19 warnings and zero errors. Full suite: 4,368 passed across 256 files in 229.86 seconds.
- Full backend: 24,155 passed and one skipped in 1,338.39 seconds.
- Four browser checks passed: sports-outlet automatic category selection and
  art-and-craft default stocking, including saved placements, photo grid and 3D
  shelf packages. The automatic store showed eight pictured packages; the default
  store showed 61, with preview racks exactly matching saved racks. The default
  flow also passed with no model configured. Both atlas endpoint galleries,
  both VLM grids and both 3D views were visually inspected.
- All six languages passed at 390 px and 1,280 px: 147 category labels, 40
  placements, preview, save-response loss, idempotent retry and opening the saved
  draft. Existing custom product names, prices and photos were retained.
- All six languages also passed actual memory replay, planning, apply and layout
  plan saving at both widths. Applied daily outcomes and weekly memory results
  matched exactly; saved run files were unchanged. Delayed and failed layout-plan
  loading blocked launch and estimates, retry restored the actual saved plan,
  and off/on preserved zero-stock overrides and hourly tills. Mobile Korean and
  desktop French launcher, starter-fill and Korean operations views were inspected.
- All 68 original atlases are included in the wheel, verified byte for byte.

Browser and API checks use disposable storage, controlled category/persona
fixtures and rule-based previews. No live model completion, local-model download
or paid simulation is required for validation.
