# Rejected optimization and study jobs release their reservations

Nine job-start paths registered pending work but did not handle executor rejection:
optimization, neighborhood synergy, A/B experiments, surveys, shelf tests,
conjoint studies, staff-script tests, shelf audits and photo/render comparisons.
An HTTP 500 could leave deletion blocked indefinitely. Thread startup errors could
also leave rejected work in the executor's queue to run later.

All these paths now use guarded submission, record a failed status with a finish
time, and return HTTP 503 with retry guidance. Marketing studies share their
existing terminal-status writer; Shelf Lab does the same with its own status
format. Optimizer cancellation flags are discarded for rejected jobs. New attempts
remain distinct jobs and preserve the failed attempt's evidence.

## Evidence

- All 18 new cases failed before their fixes: nine job types crossed with rejection
  before queue insertion and failure after insertion.
- 87 focused tests passed in 13.28 seconds for the first seven job types and
  their lifecycle, snapshot, currency and successful completion behavior.
- 20 additional focused cases passed in 5.90 seconds for Shelf Lab start/deletion
  races and rejected jobs: 107 distinct checks overall.
- Rejection tests drain real ThreadPoolExecutor queues after deleting the project
  or photo; no canceled job recreates the resource. Healthy submissions can retry.
- `uv run pyright src/`: 0 errors, 0 warnings. All checks used offline fixtures.

If the terminal status cannot be persisted because storage is also unavailable,
startup recovery may still be required; guarded submission nevertheless prevents
the rejected callable from running later.

```sh
uv run pytest tests/server/test_study_queue_failure.py tests/server/test_marketing_lifecycle.py tests/server/test_experiment_start_snapshot.py tests/server/test_synergy_start_snapshot.py tests/server/test_optimization_start_snapshot.py tests/server/test_shelf_test_integrity.py tests/server/test_staff_pitch_api.py tests/server/test_survey_currency.py -q --tb=short
uv run pytest tests/server/test_study_queue_failure.py tests/server/test_shelf_lab_start_snapshot.py -q -k shelf_lab --tb=short
uv run pyright src/
```
