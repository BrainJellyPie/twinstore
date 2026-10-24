# Rejected photo uploads can be retried

Upload acceptance reserved a capture directory and wrote its receipt, image and
pending status before queueing recognition. A persistence failure could leave
partial files, consume a stable request ID, or expose pending status for a worker
that was never queued. Retrying either failed with a conflict or returned the
abandoned pending record.

Synchronous acceptance failures now clean up the newly reserved directory and
its new receipt while holding the project tree guard. Stable-ID acceptance also
holds its existing upload lock. The original error is preserved and the same
request can be retried. Existing accepted captures bypass this cleanup; deleting
an accepted photo still retains its receipt and prevents replay resurrection.
Persistent filesystem failures during cleanup are logged, not silently hidden.

Offline verification:

- Ten fault-injection cases failed before the fix: receipt/image/status writes,
  before/after persistence, with/without stable request IDs where applicable.
  They now verify no queued worker, no pending capture or partial directory,
  no consumed retry receipt, and exactly one queued capture after retry.
- 44 focused upload persistence, project lifecycle, identifier collision and
  upload queue cases passed in 15.44 seconds. Existing accepted/deleted upload
  retry behavior and executor-start failure behavior remain covered.
- Strict Pyright on capture.py: zero errors. Recognition was mocked or used
  offline classic detection; no model services were called.
