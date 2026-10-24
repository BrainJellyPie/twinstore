# Rejected shelf-photo workers must remain canceled

ThreadPoolExecutor queues a task before trying to create a worker thread. A
startup failure therefore left a callable in the queue even though the photo
API had already marked the capture failed and returned HTTP 503. When a later
submission started a thread, the rejected capture ran. It could perform unwanted
analysis, overwrite its failure status, or recreate a photo/project directory
the user had since deleted.

Share guarded submission between photo analysis and customer generation. A
worker waits for submission to finish; if submission raises, queued callbacks
become no-ops. The guard is independent of status-file persistence. Existing
customer failure handling and capture retry receipts remain unchanged.

## Evidence

- All six new cases failed before the change: stable/legacy upload IDs crossed
  with retaining the failed photo, deleting the photo, or deleting the project.
- 86 focused tests passed in 21.16 seconds, including real offline photo analysis,
  normal uploads, receipt replay, currency defaults, project lifecycle, rejected
  customer jobs, retained evidence and generation start races.
- `uv run pyright src/`: 0 errors, 0 warnings.
- No live provider calls. Rejection tests drain real ThreadPoolExecutor queues
  after injecting failure into worker creation.

```sh
uv run pytest tests/server/test_capture_rejected_worker.py tests/server/test_capture_upload_queue.py tests/server/test_capture_upload_project_lifecycle.py tests/server/test_capture_upload_persistence.py tests/server/test_capture_default_currency.py tests/server/test_persona_queue_failure.py tests/server/test_customer_evidence_retry.py tests/server/test_customer_upload_retry_integrity.py tests/server/test_persona_generation_start_races.py -q --tb=short
uv run pyright src/
```
