# Care and home products in default maps

Added 96 products in eight departments: facial skincare, makeup accessories,
nail grooming, shaving, tea brewing, cake decorating, pantry organization and
shoe care. The catalog now has 1,592 entries across 139 categories, with 992 local
photos. Twelve matching default maps stock the new departments, preserving their
existing products and geometry. Category labels are available in all six languages.

Integrated the latest operations lab and its bounded plan search, technical report
and release-test annotations. Previous zero-stock support remains available.
Boundary checks reproduced and fixed three integration issues: plans could not
restore a profitable product starting at zero stock; non-ASCII till-hour keys were
accepted but ignored; malformed saved shopper lists could cause server errors or
be interpreted as empty visits. Invalid files now produce an actionable response
without changing the saved run.

Browser checks also exposed a saved-layout navigation race and a narrow-screen
comparison overflow. Starter saving now waits for the layout list to refresh
before offering to open the draft. A failed refresh can retry the same idempotent
save request. Wide operations comparisons scroll inside their panel, keeping the
last column reachable and money values separated.

Validation on 2026-10-22:

- Stock and operations boundary checks: 79 passed in 18.24 seconds, including
  zero-stock profitability, invalid hour keys, both ordinary and shared runs with
  malformed saved visits, and unchanged saved files after replay or planning.
- Focused backend: 7,171 passed in 411.48 seconds, including 108 new default-map,
  currency and seed cases plus 36 small-map limit/exclusion cases.
- Strict backend types: zero errors; application boot passed.
- Full backend: 23,432 passed and one skipped in 1,252.52 seconds.
- Full frontend: 4,342 passed in 253 files in 243.13 seconds. Build passed in
  24.26 seconds; lint retained 19 warnings and zero errors. The two navigation
  regression tests failed before the fix; all 54 focused starter/localization/lab
  checks passed afterward in 6.64 seconds.
- Browser automatic beauty-store creation passed with four new care departments;
  realistic rendering loaded eight pictures. Default tea-lounge creation used
  stocked format defaults without a configured model; saved racks exactly matched
  the preview, and realistic rendering loaded 55 pictures. All 32 new image
  endpoints, two galleries, both VLM grids and both 3D views passed inspection.
  VLM grids display the picture, product name and price together where available.
- All six languages passed at 390 px and 1,280 px: all 139 category labels,
  stock preview, saving after a lost response, opening the saved draft, and
  preservation of the original layout and custom product names/prices/photos.
  Korean mobile and French desktop starter previews were visually inspected.
- The operations lab passed actual replay, planning and applying/replaying the
  proposed plan in all six languages at both widths. Invalid costs/hourly till
  counts were blocked; the final comparison column remained reachable through
  the scrolling table. Saved run files stayed byte-identical. Korean and Spanish
  mobile plus French desktop comparisons were visually inspected.
- All 62 original atlases are included in the wheel, verified byte for byte.

Product selection and persona creation used controlled browser fixtures in
disposable storage. Operations replay/planning used completed rule-based previews.
No live provider completion, local-model download or paid simulation was invoked.
