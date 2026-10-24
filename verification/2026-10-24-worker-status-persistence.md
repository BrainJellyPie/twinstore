# Background workers recover failed status commits

Ten background job paths wrote their initial running status before entering
their exception handler. A transient atomic-replacement failure escaped the
worker and left the saved job pending indefinitely, blocking deletion or retry.
Photo analysis, optimization and neighborhood synergy also wrote their terminal
status outside failure handling, leaving finished computations marked running
when that write failed.

The existing handlers now cover the initial commit for optimization, synergy,
photo analysis, experiments, surveys, shelf comparisons, conjoint, staff scripts,
Shelf Lab audits and sim2real. Photo and synergy completion commits run inside
the same handler. Optimization catches terminal status failures, including
cancellation, and records a failed job. Already saved result files are retained;
this recovery does not repeat analysis or model calls.

## Evidence

- All ten initial-status regression cases failed before the change.
- Four additional cases reproduced completion failures for photo analysis,
  optimization and synergy, and a cancellation-status failure for optimization.
- Fault injection targets the actual atomic JSON replacement. The previous
  pending/running record remains intact until the failed status commits.
- All fourteen cases now finish with a saved error and finished timestamp,
  release project deletion, and leave no project directory after deletion.
  Completion cases keep the calculated result before deletion. Cancellation
  clears its in-memory request without starting the search.
- 71 focused checks passed in 16.59 seconds, including existing worker queue,
  optimization cancellation, photo upload and failed synergy evidence coverage.
- Strict Pyright: zero errors and warnings. Fake computation and offline photo
  fixtures only; no live model calls.

Recovery still requires storage to accept the failed-status write. Persistent
filesystem failure or process termination cannot be repaired by this handler.

```sh
uv run pytest -q tests/server/test_worker_status_persistence.py tests/server/test_study_queue_failure.py tests/server/test_rule_optimization_cancel.py tests/server/test_optimization_cancel_projects.py tests/server/test_capture_upload_queue.py tests/server/test_town_synergy_failed_evidence.py --tb=short
uv run pyright src/
```
