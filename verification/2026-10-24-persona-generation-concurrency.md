# Honor customer-writing concurrency across weekdays

The shared semaphore used max(max_concurrent, 20). A requested limit of 1, 2 or
10 therefore allowed 20 simultaneous customer-writing requests, including with
the default limit of 10. A simulated provider accepting ten concurrent requests
rejected the excess batches and caused generation to fail.

The shared semaphore now uses the requested limit, bounded below by one. All
weekdays still share it; the budget is not multiplied by the number of open days.
Limits above 20 remain supported. This controls customer-writing batches, not
the separate location/traffic analysis calls.

Offline verification:

- 17 new cases cover 1/2/7 weekdays, limits 1/2/10/20/25, the default limit and
  a provider rejecting work above its configured capacity. Eleven failed before
  the fix. All now preserve the complete population without rejection or twins.
- 89 focused concurrency, sample-probe, missing-day and empty-generation tests
  passed in 3.07 seconds. Four additional existing tests failed because their
  shared model stub lacked api_base; the same four failures were confirmed on
  unchanged main. Supplying api_base=None in that stub restored the intended
  failure/preservation checks, which passed in 2.25 seconds (93 distinct cases).
- Strict Pyright on the changed generator module: zero errors.

Model clients were scripted in memory; no provider services were called.
