# Consistent capture corrections and counterfactual images

Capture correction could interleave its product list, overlay and status writes with
another correction, leaving different versions in one capture. Correction and photo
edit writes could recreate deleted capture/project directories. Study startup could
also read a capture during correction, or lose a counterfactual image while copying it.

Capture correction now uses the existing project tree transaction and prepares the
overlay before changing the saved result. Counterfactual creation snapshots its source
and package images under that transaction, processes images outside it, then rechecks
the source and commits under the transaction. Changed sources return 409; deleted
sources return 404. Counterfactual deletion uses the same transaction as study input
capture. Package file handles close after copying their pixels.

Validation used temporary projects, fake model configuration and paused executor jobs:

- After correcting the initial test fixture import and PUT request shape, **12
  regressions failed in 3.72 seconds** on the original code.
- The first guarded implementation passed 26 of 30 focused tests, including 18 existing
  startup/API tests. Four test assertions incorrectly expected capture deletion to return
  200 instead of its documented 204; these assertions were corrected.
- After moving image processing outside the lock and adding source-change/final-commit
  cases, all **14 new transaction tests passed**. Three existing correction tests needed
  their fixture to create the parent project metadata now required by the transaction.
- Those six existing correction tests and two added image/overlay preparation failure
  cases passed: **8 passed in 2.99 seconds**. Preparation failure leaves saved product
  data and status intact. Overall, the final capture transaction/correction coverage
  comprises **22 distinct passing tests**, without repeating the full suite.
- Strict Pyright for both changed application modules: **0 errors**.

Logs: `/workspace/scratch/capture-edits-{before,after,final,final-extra,types-final}.log`.
The transaction coordinates application operations; it is not a multi-file filesystem
rollback mechanism for arbitrary disk-write failures. No live provider calls were made.
