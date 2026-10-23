# Dense neighborhood demand without unused share cubes

The demand model retained a group × venue × 24-hour share array for every venue category.
Direct demand only read the focal store's column, and complementary demand discarded the
entire array. A valid generated neighborhood (`size_m=3000`, `density=1`, `venue_density=4`,
seed 24102490) contains 11,318 buildings, 1,884 venues and 13,767 origin groups. The largest
unused share cube would occupy 1,134.4 MiB, independent of the other working arrays.

`_huff_flows` now optionally retains one focal column as group × hour shares. Complementary
flows request no saved shares. Per-hour shares and matrix products are otherwise unchanged;
the model still accounts for every origin and venue without sampling or truncating the town.

- Before: the subprocess constrained to 512 MiB above its existing virtual memory failed
  trying to allocate an 852 MiB intermediate cube; the regression failed in 1.41 seconds.
- After: the same public demand calculation completed in 1.539 seconds, peak process RSS
  387.8 MiB. The subprocess test, including generation/imports/JSON output, passed in 3.57 seconds.
- Exact before/after JSON comparison: 42 public outputs identical, spanning all seven town
  archetypes, weekday/weekend/holiday and empty/all-day hour sets (seed 24102491).
- Related town, origin, linked-trip, scenario traffic and town API checks: 156 passed in
  18.75 seconds. Strict Pyright for `town/demand.py`: zero errors/warnings.
- The resource-budget regression uses Linux `/proc` accounting and skips on other platforms.
  No live map/model requests, frontend changes or full suite.
