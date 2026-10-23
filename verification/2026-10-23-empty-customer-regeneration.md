# Preserve customers when regeneration has no operating days

Missing/empty weekly schedules or an entirely closed schedule passed the background generation path,
called the model for trade-area analysis, then completed with zero customers. The worker overwrote the
saved population with an empty list. Validate that an open weekday exists before starting the async
pipeline; report a failed generation with operating-schedule guidance and preserve the saved population.

Focused evidence:

- Missing schedule, empty schedule, one closed day and seven closed days (including 0–0 closed hours).
  Assert failure, no model setup/call and byte-for-byte preservation of customers and metadata.
- Confirm existing protection for open-day traffic calibrated to zero, both with and without old customers.
- After excluding an artificial test that bypassed the existing open-day guard, the baseline was
  **4 failed, 2 passed in 2.09s**.
- New cases plus missing-day, metadata-write and duplicate-schedule checks: **54 passed in 6.68s**.
- Strict Pyright on the changed module: **0 errors**.

Empty legacy layout schedules remain supported by the domain and simulation. This guard applies when
generating replacement customers. No live model calls, full suite, frontend or release binary changes.
