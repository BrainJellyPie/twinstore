# Checkout completion contributes to staffing cost

A store opening 21:00–22:00 with ten late shoppers and one till could perform
100 minutes of checkout service but report only 60 staffed minutes. The last
checkout ended at 23:39:55, yet labor cost at 1,000 per hour stayed 1,000 instead
of 2,670. Crew mode already tracked completion events, so otherwise identical
staffing models disagreed and could distort plan comparisons.

The shared resolver now advances the accounting horizon to every completed
checkout's finish. Queue ordering and customer patience are unchanged. Boundary
tests also exposed zero-second service being mistaken for an unset duration:
zero now stays zero, while stores without tills retain their original timeline.

Validation:

- Before repair, the 72-case matrix had **37 failures and 35 passes**, 0.80 s.
  Cases vary scheduled/legacy hours, 1–3 tills, 0/1/30/600-second service and
  1/2/10 customers. Every case compares till hours, cost and utilization against
  the completed timeline and against crew mode with no shelf work.
- The accounting fix alone left six zero-service failures, identifying the
  separate unset-duration ambiguity. Both repairs pass the complete matrix.
- Engine and API checks: **738 passed**, 25.50 s. Additional controls preserve
  input data and stores without tills. The replay API reports 2.67 staffed hours,
  labor cost 2,670 and utilization consistent with all 6,000 service seconds.
- Strict backend types: **zero errors/warnings**. App import: **OK, 235 routes**
  in the worktree without the built frontend's two static routes.
- Frontend source is unchanged from the previously verified snapshot: 4,479
  tests, build and lint passed for that exact frontend source.

Full backend verification will be recorded before publication. Tests use
synthetic visits, with no live model calls.
