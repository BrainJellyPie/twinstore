# Share calculations across neighborhood removal effects

The synergy endpoint rebuilt every origin/category demand calculation and report for the
baseline and then once per other venue. A supported dense 3 km neighborhood has 1,884 venues;
its old loop would require 1,884 complete demand evaluations. That largest old loop was not
run. The default demand call retains its normal path; synergy alone opts into removal effects.

For each Huff choice set, removing utility `u[k]` changes a group's expected focal reward
by `u[k] / (D - u[k]) * (reward[k] - E)`, where D includes the outside option and E is the
original expected reward. Direct store choice and complementary-venue choice share this
calculation. Removing a rival store also recomputes source venues' chaining probabilities
with that store's pull removed, including the existing capped total chaining probability.
Every venue is retained. Baseline/without totals are rounded separately before subtraction,
matching the original public report semantics.

- Baseline regression: 1 failed, 12 passed in 3.54 seconds. An 8-venue town made 8 complete
  evaluations; the new implementation uses one.
- Initial exactness/type checks: 13 passed in 1.91 seconds; strict Pyright zero errors/warnings.
- Local benchmark (one OpenBLAS thread): 149-venue town, old explicit removal 10.820 seconds,
  shared calculation 0.091 seconds; all 148 effects exactly equal.
- Maximum supported generated fixture: 1,883 non-focal rows in 3.885 seconds, peak RSS
  434.8 MiB, within 512 MiB of extra address space and a 30-second subprocess timeout.
- Final focused suite: 44 passed in 19.20 seconds, including dense demand memory, exact
  explicit-removal comparisons, town engine behavior and town API tests.
- Exactness cases cover all venue categories, simultaneous substitute/complement effects,
  non-convenience focal stores, overnight/full-day/closed hours, weekdays/weekends/holidays,
  modified attractiveness/outside options, zero distance decay, zero traffic and empty origins.
- Resource regression uses Linux process accounting; no live maps/models or full suite.
