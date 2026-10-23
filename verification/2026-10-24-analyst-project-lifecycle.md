# Run analyst and project deletion

An analyst reply kept its original transcript path during the model call. Deleting the
project while that call ran succeeded, but the returning reply recreated the run folder
and wrote an orphaned analyst transcript. A lock acquisition after deletion could also
recreate the parent directories before the next run-existence check failed.

The project tree guard now protects transcript-lock acquisition and the initial thread/fact
snapshot. The provider call runs outside that guard. The final save rechecks the run under
the same guard; clearing a thread also coordinates its lock/file changes with deletion.
The existing nonblocking transcript lock continues to reject simultaneous ask/clear operations.

- Before: all 10 new lifecycle cases failed in 3.33 seconds.
- After: 27 passed in 9.04 seconds, including analyst API/error handling, ask/clear conflicts,
  and adjacent POS/movement report lifecycle tests.
- Boundary cases: existing/empty conversation, deletion during answer generation, deletion
  during persistence, deletion starting first, deletion just before lock-file creation, and
  tree-lock contention for both asking and clearing.
- Strict Pyright for `application/run_analyst.py`: zero errors/warnings.
- Temporary projects and fake providers only; no live model calls or full suite.
