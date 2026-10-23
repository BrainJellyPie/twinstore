# Reserve venue-synergy startup against input saves and deletion

Synergy startup read project inputs and registered pending status without the transaction used by
project deletion and input saves. Deletion could erase an accepted job or finish before late pending
registration recreated the job directory. A save already in progress could leave the study on stale
customers or layout data.

Hold the existing project/layout transaction from input loading through pending-status registration.
The background computation remains outside the transaction. Existing pending-job checks then block
project deletion until accepted work finishes.

Focused evidence:

- 12 new API cases cover explicit/focal-derived layouts, both orderings of deletion and startup,
  customer/layout saves already in progress, and busy tree/layout locks without stray jobs.
- Before the fix, deletion/save/lock cases failed. Two layout cases initially used a service-level
  fixture missing API response fields (`runId`, `memo`, `created_at`); corrected that fixture before
  claiming coverage of the layout API race.
- Corrected new cases: **12 passed in 4.90s**. Existing town API and saved-customer validation cases:
  **54 passed** in the preceding combined run (64 passed plus the two fixture errors, 16.03s).
- Strict Pyright on the changed module: **0 errors**.

No live model requests, full suite, frontend or release binary changes. This protects study acceptance;
it does not change editable neighborhood persistence or executor shutdown handling.
