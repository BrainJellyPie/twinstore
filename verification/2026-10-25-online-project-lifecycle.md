# Keep active online jobs attached to their project

Project deletion checked the other background-job directories but omitted
`online/runs/*/status.json`. An accepted online run could therefore lose its
inputs while its worker was still pending or running. Its later writes could
also recreate an orphaned directory under the deleted project.

The existing project deletion guard now includes online runs. The shared project
tree lock orders deletion against online snapshot/job registration: an accepted
job makes deletion return 409; a completed deletion makes a later start return
404 without submitting a worker. Once the worker finishes, deletion is allowed.

Before repair: **5 failed, 22 passed in 4.09 seconds**. Tests cover pending and
running jobs, preservation of saved snapshots, actual deterministic rule-worker
completion, cleanup afterward, and both orders of concurrent start/delete.
Related project job/path/restart and online API regressions passed after repair:
**82 tests in 6.80 seconds**. Full-source Pyright: **0 errors, 0 warnings**.
No model calls were made, and only temporary test projects were deleted.
