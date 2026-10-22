# Pet, garden and craft products in default maps

Added 96 products across pet walking, car detailing, composting, watering and
irrigation, embroidery, knitting and crochet, paper crafting and food gift
packaging. Twelve matching default maps stock the new departments while keeping
existing products and valid geometry. The catalog contains 1,784 entries in
155 categories with 1,184 photos in 74 atlases. New category labels are available
in all six interface languages.

Integrated reconstruction of missing summary metrics for older saved runs,
without rewriting their files or running another simulation. Unknown purchase
origins still leave impulse share empty. Four boundary regressions showed that
cached enrichment ignored changed store, persona and heatmap files and could
be shared across copied data folders. Cache keys now use the absolute data
folder and versions of all five input files. New code uses explicit object types
and validates saved shapes; damaged data retains its original summary.

Validation on 2026-10-22:

- Four cache regressions failed before the fix; the initial six summary checks
  then passed in 7.59 seconds. The expanded 12 checks passed in 13.86 seconds,
  covering changed/corrupt sources, separate data folders, modern zero/partial/full
  conversion values, missing optional summary inputs and repaired timelines.
  The summary API still requires its separate persona response; the optional
  input checks correctly exercise the reconstruction service.
- New default departments across currencies, seeds and small-map limits:
  144 passed in 2.17 seconds. New image endpoint checks: 46 passed in 5.51 seconds.
- Strict backend types: zero errors; boot passed. Full backend:
  24,951 passed and one skipped in 1,269.23 seconds.
- Focused dashboard, category-selection and package checks: 84 passed in
  8.42 seconds. The prepared category fixture accidentally duplicated shoe care;
  it now retains camping repairs alongside the eight new categories.
- Frontend build passed in 21.59 seconds. Lint retained 19 warnings and zero errors. Full suite: 4,396 passed across 256 files in 228.64 seconds.
- Four product browser checks passed: automatic craft-store selection and default
  garden-center stocking, including real create and VLM chart APIs, preview racks
  matching saved racks, and default stocking with no model configured. The 3D
  stores loaded all six and all 71 expected product photos. Both endpoint galleries,
  both VLM grids and both 3D stores were visually inspected.
- Actual older-run summaries passed in all six languages at 390 px and 1,280 px.
  Conversion, basket and units matched the API; unknown impulse share stayed
  blank, saved totals remained intact and all saved run files stayed byte-identical.
  No new run was started. Korean mobile and French desktop results were inspected.
- All 155 category labels and starter selection/preview/save/retry passed in all
  six languages at 390 px and 1,280 px. Each case saved 40 placements, recovered
  a lost save response idempotently and preserved the original custom product.
  Korean mobile and French desktop results were visually inspected.
- All 74 original atlases are packaged in the wheel, verified byte for byte.

Validation uses disposable data, controlled product/persona fixtures and saved
sample runs. No live model completion or paid simulation is needed.
