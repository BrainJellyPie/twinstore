# Share town geometry while describing visitors

Every direct visitor description scanned the full building list and all venues to find its
origin and nearest competing convenience store. This work repeated for cloned shoppers from
the same origin, across every day of a run. The full visitor preparation also happens before
the simulation's customer cap and in its cost estimate.

A batch writer now indexes the snapshot's buildings and convenience stores and computes the
nearest rival once per encountered origin. A run shares it across days; synergy uses separate
writers for the with-venue and without-venue towns. No persistent cache can leak distances
between requests or counterfactual towns. The single-arrival helper remains available and
both paths use the same formatter.

- Baseline public preparation regression: 2 failed in 0.79 seconds. The two-day case looked
  up buildings 2,888 times for 114 unique origins.
- Related town/arrival/synergy checks: 177 passed in 16.14 seconds. The two new counting tests
  initially included unrelated demand-model distance calls; their instrumentation was scoped
  to the arrival module, then both passed in 0.46 seconds. No production change was needed.
- Strict Pyright for all changed modules: zero errors/warnings.
- Exact before/after snapshots: 3,619 unchanged strings over all seven town archetypes and
  weekday/weekend/holiday profiles (seed 24102492).
- Supported dense 3 km town, density 1, venue density 4, seed 24102490, arrival scale 5:
  17,695 visitors; cProfile-instrumented preparation fell from 6.648 to 2.582 seconds.
  The original description loop accounted for 4.041 seconds of the former run.
- Benchmark used one OpenBLAS/OMP thread locally; this is not a cross-machine latency guarantee.

No model requests, frontend changes or full suite. Existing complete-pair synergy behavior
and visitor identities are unchanged.
