# Preserve time-specific building origins

Direct arrival origins still used building/age totals over the whole day. The same mistake affected
replacement origins when a linked venue was removed in a synergy study. In a hotel/hospital fixture,
5 of 77 visitors at 23:00 were attributed to the hospital although that hour's modeled visitor demand
came entirely from the hotel. Changing noon traffic could also change other hours' sampled origins.

Retain building flows by hour and age in demand reports, use them in direct and counterfactual draws,
and sort counterfactual candidates by stable building/segment keys. Older reports without those flows
retain their available daily weighting. No population priors or total demand formulas change.

Focused evidence:

- 25 new checks: weekdays/weekends/holidays, three seeds, complete or missing age groups, hourly flow
  sums, midnight/early/late counterfactuals, report reordering, paired noon traffic changes and legacy data.
- Before the fix: **24 failed, 1 passed in 0.69s**.
- New checks plus existing town/arrival/linked-origin tests and completed offline synergy comparison:
  **99 passed in 11.62s**. Strict Pyright on three changed modules: **0 errors**.
- Broadened randomized exploration (seed 1042386): 180 towns, 2,721 visitors. Source exposure/age
  conditions found one failing town before the fix (**0.382s**) and none after (**0.465s**).
  An initial oracle based on rounded report rows also flagged two tiny flows omitted from those reports;
  checking the underlying modeled presence distinguished these from the actual zero-exposure defect.

Scratch script: `/workspace/scratch/explore_town_origin_boundaries.py`; before/after reports:
`town-origin-exposure-before.json` and `town-origin-exposure-exploration.json` in the same folder.
No live model requests, full suite, frontend or release binary changes. New reports contain additional
source-weight data; older reports cannot reconstruct hourly weights they did not retain.
