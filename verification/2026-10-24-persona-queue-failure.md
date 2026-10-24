# Customer generation rejected by its worker

Worker shutdown and initialization failure left a pending customer-generation
record after returning HTTP 500. That record prevented another generation,
simulation starts and project deletion until startup recovery ran.

Mark a rejected submission failed and return HTTP 503. Coordinate submission
with the worker's initial state transition: Python's ThreadPoolExecutor can put
the task in its queue before thread startup raises. A canceled start must not
run when another thread eventually drains that queue. The in-memory cancellation
signal remains effective even if writing the failed status also fails.

Existing customers and retained attachments are preserved. Completed, failed
and missing generation records are not restarted by a delayed worker.

## Evidence

- The four initial regression cases all failed before the fix: shutdown and
  broken worker initialization, with and without retained customer uploads.
- 82 focused cases passed in 7.90 seconds, including generation/run/deletion
  races, retained evidence and generation validation.
- One additional status-write failure case plus the six related regression
  cases passed in 3.26 seconds: 83 distinct cases overall.
- Real ThreadPoolExecutor queues were drained after injected worker-start
  errors, checking both retained and subsequently deleted projects.
- `uv run pyright src/`: 0 errors, 0 warnings. No live model calls.

If storage also refuses the terminal status write, the API returns an error and
the persisted pending record still needs startup recovery after storage is
available. The rejected queued task nevertheless remains canceled.

```sh
uv run pytest tests/server/test_persona_queue_failure.py tests/server/test_persona_generation_start_races.py tests/server/test_customer_evidence_retry.py tests/server/test_customer_upload_retry_integrity.py tests/server/test_persona_generation_missing_project.py tests/server/test_duplicate_weekday_schedule_api.py tests/engine/test_empty_customer_regeneration.py tests/engine/test_persona_missing_days.py -q --tb=short
uv run pyright src/
```
