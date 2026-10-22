# Complete pet, garden and craft default-map photos

Adds the remaining 64 photos for pet walking, car detailing, composting,
watering and irrigation, embroidery, knitting and crochet, paper crafting and
food gift packaging. The eight departments have a photo for every product in
the matching default maps. The catalog contains 1,784 entries in 155 categories,
with 1,248 local photos in 78 atlases.

Integrated the latest shared crew for checkout and shelf refills, including
hourly staffing, labor costs, planning and six-language results. Preserved prior
stock validation, long browsing stops, empty-backroom reporting and saved-layout
loading protection while resolving the integration conflicts. The six-language
labor-cost label now includes both checkout and refill staff.

Eight boundary checks reproduced shoppers waiting unnecessarily when a pick or
refill completion coincided with their arrival at the till. Refill dispatch now
runs after payments at the same timestamp. Eighteen six-language checks exposed
crew result rows disappearing at zero staffed hours; comparison columns now read
their actual configuration to determine which rows apply. Six additional checks
exposed a planner returning an invalid zero default crew when all hours were
unstaffed. Only positive staffing values become the default; zero hourly
exceptions remain explicit and the plan can be validated and replayed.

Validation on 2026-10-22:

- Checkout/refill regressions: eight failed before, then eight passed in 0.41 s.
- Crew, backroom conservation, replay and API checks: 420 passed in 25.81 s.
  Inventory coverage includes one, two and four crew, finite and zero backrooms,
  per-product overrides, deliveries and all seven days; shopper inputs are kept.
- Zero-hour crew rows: 18 failed before. The corrected operations interface and
  loading fixture passed 127 checks in 6.28 s. The fixture now waits for saved
  settings before changing the crew input, matching its disabled loading state.
- Unstaffed-day plans with default crews of 1, 2 and 100 and zero/short search
  budgets: six failed with the prior normalization in an isolated process, then
  six passed in 0.72 s. An initial test fixture used invalid zero patience; it
  was corrected to the supported 10-second minimum before the final run.
  The initial full backend run was stopped after 2,734 passes to include this fix.
  A subsequent run reached 71% without failures before the managed environment
  restarted; source hashes stayed identical and the full suite was restarted.
- Strict backend types: zero errors; boot passed. Full backend: 25,565 passed,
  one skipped in 1,340.86 s.
- Final frontend build passed in 19.63 s; lint retained 19 warnings and zero
  errors, and all 4,433 checks across 256 files passed in 225.34 s.
  Focused product package checks: 63 passed in 0.529 s.
- New image endpoints: 84 passed in 9.85 s. Complete default-map assortments:
  36 passed in 0.93 s across USD, KRW and JPY.
- Four actual product browser checks passed: automatic craft-store selection,
  no-model default garden stocking, preview matching saved racks and both 3D
  stores loading every expected photo (six and 87). All four endpoint galleries,
  both VLM grids and both 3D stores were visually inspected. Two 60-second clicks
  on an already-selected garden layout timed out under parallel software-rendering
  load. The final check waited for all 87 photo resources before interacting and
  only selects the layout when needed; the application was unchanged.
- Actual crew results, replay, planning and layout saving passed in all six
  languages at 390 px and 1,280 px. Zero-hour rows stayed visible, staffed crews
  refilled shelves, applied plans reproduced outcomes and two-week memory results,
  and saved hourly staff settings survived delayed loading, a 503 retry and
  off/on toggles. Every saved run file stayed byte-identical; no extra run was
  started by the UI. Korean and French zero-hour and comparison views were inspected.
  Five languages completed before the environment restart; French completed on
  an equivalent fresh disposable run after recovery.
- Final staff-cost wording passed a separate real replay in all six languages,
  with zero-hour rows present and every saved run file unchanged. Korean mobile
  and French desktop views were visually inspected. No extra run was started.
- All 78 original atlases are packaged in the final wheel, byte for byte.

Validation uses disposable data and controlled model fixtures. No live paid model
completion is used.
