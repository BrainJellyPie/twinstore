# A rejected simulation must release its layout

The run API marked a layout running and reserved a pending run before submitting
its background work. Submission failure returned HTTP 500 without releasing
either state, preventing the next run and project deletion until restart.

Use guarded background submission and the same failure finalization used by
simulation execution. Return HTTP 503 after restoring a non-preview layout to
draft and recording a failed run. Previews leave the source status and existing
run link untouched. Layout notes, store contents and snapshot metadata remain
intact. As with other failed runs, the rejected attempt keeps its run ID; a
subsequent run uses a new ID.

## Evidence

- All 14 new cases failed before the change.
- 79 focused tests passed in 39.97 seconds: rule/vision starts, worker shutdown
  and broken initialization, preview/final runs, draft/finalized sources,
  retries, persistence rollback, terminal status ordering, concurrent edits,
  startup recovery and image snapshots.
- A real executor queue was drained after injected thread-start failure and
  project deletion; the rejected simulation did not run or recreate files.
- `uv run pyright src/`: 0 errors, 0 warnings. No live model calls.

Persistent storage or lock failures can still prevent state restoration; the
existing failure logger/startup recovery remains responsible for those cases.

```sh
uv run pytest tests/server/test_simulation_queue_failure.py tests/server/test_run_start_persistence.py tests/server/test_run_terminal_state_order.py tests/server/test_simulation_setup_races.py tests/server/test_simulation_recovery.py tests/server/test_simulation_image_snapshot.py -q --tb=short
uv run pyright src/
```
