# Keep late photo uploads from recreating deleted projects

The upload checked project existence only before photo decoding/model preparation. Deleting the project
during that work still let the upload recreate image folders and register recognition afterward.
Deletion could also pass its active-job check while an upload had not yet written pending status.

Recheck project existence under the existing tree transaction when committing the image, retry receipt
and pending status. Keep expensive preparation outside that transaction. Stable-ID uploads use a lock
in the existing nonremovable lock directory and check replay/tombstone state under the tree transaction;
decoding never needs to recreate a deleted project merely to obtain an upload lock.

Focused evidence:

- Ordinary/stable uploads × deletion during decoding/model setup; retries leave deleted projects absent.
- Both orderings of commit and deletion: accepted work blocks deletion, completed deletion blocks upload.
- Before the fix: **8 failed in 3.50s**.
- New cases plus real classic-detector acceptance/retry/deletion/concurrent-retry and rejected-executor
  checks: **12 passed in 7.57s**.
- Strict Pyright on the changed module: **0 errors**.

No live model calls, full suite, frontend or release binary changes. Existing upload IDs, digests and
deletion receipts keep their meaning; only the transient upload lock moves to the normal lock directory.
