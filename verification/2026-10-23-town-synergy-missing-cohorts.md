# Missing visitor groups in neighborhood revenue predictions

Neighborhood basket studies simulate affected visitors in both venue conditions
and unaffected visitors once. Previously, losing every affected pair silently
set the basket effect to zero. Losing the unaffected group substituted spending
from the affected group, even when the missing group represented most visitors.
An entirely failed run could publish a completed zero-revenue report.

The engine now requires successful evidence for every group present in the
modeled population, including complete pairs for affected visitors. A missing
required group raises a clear error; the existing job handler marks the job
failed and publishes no revenue report. Missing first-panel evidence stops before
the second panel. Positive traffic with no sampled visitors is also unavailable.

Groups absent from the population need no results. A genuinely closed, zero-traffic
day remains valid, as do successful zero-purchase visits. Partial failures remain
usable when both required groups have evidence; original population weights and
paired exclusions are preserved, with failure counts and warnings.

Verification:

- Initial reproduction: 16 failed and 5 passed in 1.39 seconds.
- Related engine and API checks: 40 passed in 6.86 seconds.
- After adding early termination, all 22 affected engine/API cases passed in
  4.04 seconds. Pyright on the changed engine module passed.
- Covers all failures, either affected arm missing, disjoint successful IDs,
  missing unaffected visitors, different sample sizes/seeds, partial failures,
  all-affected/all-unaffected populations, valid zero purchases and empty samples.
- Existing opening-hour, closed-day, currency and scenario tests stayed green.
  The API regression used a failing offline engine through the actual job runner
  and confirmed a failed status, null result and no result.json artifact.

This prevents unsupported predictions; it does not repair selection bias among
the remaining successful customers or change the demand model. No live model
calls or frontend rebuild were needed.
