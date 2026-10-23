# Terminal run status follows its layout transition

The worker published `completed` or `failed` before changing the source layout
from `running` to `locked` or `draft`. The frontend stops polling on a terminal
run status and invalidates layout queries once. A poll while the layout write
was waiting could therefore cache the old `running` state as its final refresh.

The layout transition now precedes terminal status publication. Preview runs
continue to leave the source layout unchanged. If completion publication fails
after the layout was finalized, failure cleanup clears only that run's `runId`
as it restores the draft, so the failed run does not keep the editor locked.
The existing best-effort handling of persistent storage/finalization errors is
retained; this change is not a multi-file crash transaction.

Focused verification with temporary projects and rule-only shoppers:

- Original-code API-poll reproduction paused the layout write for both success
  and failure: **2 failed, 2 preview cases passed in 3.83 seconds**.
- Added completion-status write failures before/after the write for final and
  preview runs. They require a failed status with no stale final-run lock.
- Final new cases plus existing editor/finalization races and schedule failures:
  **29 passed in 8.56 seconds**.
- Strict Pyright for `application/simulation.py`: **0 errors**.

No provider calls, full suite or frontend build were repeated.
