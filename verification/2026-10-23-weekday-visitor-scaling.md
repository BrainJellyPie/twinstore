# Keep financial traffic scaling local to each weekday

Given 1,000 saved Monday customers representing 10,000 visits and 100 Tuesday customers representing
100 visits, the previous global estimate/sample ratio reported **918.2** Tuesday visitors when only
Tuesday was analyzed. A separate completed A/B reproduction reported **1,673.3** instead of **40**.
These visitor counts multiply per-visitor money in experiment and shelf-audit reports.

Read estimates once, retain a count/estimate per weekday, and scale only customers arriving on each
included day before averaging those active days. Round only the final averages. Missing, nonnumeric,
negative, nonfinite or overflowing day estimates use the day's observed population; other usable
estimates remain intact. Preserve the existing floor at observed customers and active-day convention.

Focused evidence:

- Seven selected weekdays crossed with three own-day and three unrelated-day scales; different sample
  sizes, partial opening hours, multiplied scenario arrivals, absent/corrupt metadata and empty arrivals.
- A completed offline A/B report verifies that the corrected scale reaches the report.
- Before the fix: **71 failed, 9 passed in 3.94s**.
- New cases, existing experiment shopper tests and traffic-snapshot checks: **88 passed in 4.72s**.
- Strict Pyright on the changed module: **0 errors**.

No live model calls, full suite, frontend or release binary changes. Already saved reports are not
rewritten. The estimate still assumes customers retained within one weekday represent its traffic.
