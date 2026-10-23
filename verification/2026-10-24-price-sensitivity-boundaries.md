# Price-sensitivity intersections independent of chart resolution

The Van Westendorp calculation previously interpolated intersections on 60 evenly
spaced prices between the lowest and highest answer. With nine responses at
100/200/300/400 minor units and one at 100/200/300/100,000,000, the reported optimal
price became **877,292**, although the relevant curves meet inside the ordinary
response range. Changing chart resolution changed the recommendations as well.

Intersections now use every observed threshold and its adjacent minor units, with
sorted thresholds and binary searches for cumulative counts. Calculating intersections
from integer counts also preserves exact ties that floating-point complements could
miss. The final price is checked for equality. The existing curve-pair definitions
and first-intersection convention are retained.

Chart sampling is separate: it samples observed transitions, retains the reported
points and neighbouring units, and stays at no more than 73 points with the default
60-step setting, including a 1,000-respondent panel. Response filtering and minimum
usable panel requirements are unchanged.

- Initial regressions: **13 failed, 3 passed in 0.62 seconds**. These cover a large
  outlier, three currency scales, five plotting resolutions and final-point equality.
- A subsequent 60-case exhaustive integer-price oracle found the existing floating
  tie issue (one marginal point was 21 instead of 17), fixed by using integer counts.
- Final focused suite: **49 passed in 8.24 seconds**, including the exhaustive oracle,
  survey responses, currency handling, CSV values and report rendering.
- Strict Pyright for the changed engine module: **0 errors**.

Logs: `/workspace/scratch/price-sensitivity-{before,after,final,types-final}.log`.
No live models were called. This repairs numerical evaluation of the existing method;
synthetic survey results remain model responses, not observed customer demand.
