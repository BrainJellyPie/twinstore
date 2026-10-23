# Customer-generation choice handoff

The confirmation endpoint published a choice before updating progress. The waiting worker could consume
the choice and finish or cancel before that progress write, which then changed its terminal status back
to running. A project could remain stuck with no active worker. Overlapping confirmations also both
succeeded and could replace each other's selection.

Each generation now has a file lock shared by the confirmation endpoint and the waiting worker. The
endpoint validates the current confirmation, writes the choice and updates progress while holding it.
The worker consumes the choice only after that handoff commits; another confirmation then returns 409.
Busy confirmations return 503. The existing HTTP route already runs in the thread pool.

The deadline is checked inside that same lock, after checking for an accepted choice. Expiry closes the
confirmation window before the worker records failure, preventing an answer being accepted in between.
An already accepted choice is consumed even if its progress write crosses the deadline. A failed choice
file write preserves the original confirmation for retry.

Validation used temporary generation records, real file locks, controlled concurrent requests and the
actual choice consumer. No model calls were made.

- Initial regression matrix before changes: **14 failed, 3 passed in 3.43 s**.
- Additional deadline probes reproduced two failures after the initial handoff change; both were fixed.
- Final focused run: **29 passed in 8.44 s**, covering completion, failure, cancellation, all nine pairs
  of overlapping answers, write failure/retry, deadline handoff and expiry, busy/unrelated jobs, missing
  records, existing write-size selection behavior and generation project existence.
- Strict Pyright on the changed module: **0 errors, 0 warnings**.
- `git diff --check`: clean. No frontend or full-suite rerun for this backend-only fix.

Commands (from `backend/`):

```bash
.venv/bin/pytest -q tests/server/test_generation_choice_handoff.py tests/engine/test_write_choice.py tests/server/test_persona_generation_missing_project.py --tb=short
.venv/bin/pyright src/store_emulator/application/generation_async.py
```

This fix prevents new stuck jobs; existing interrupted jobs continue to use startup recovery. It is a
main-branch fix after v0.4.11 and does not change the published release archives.
