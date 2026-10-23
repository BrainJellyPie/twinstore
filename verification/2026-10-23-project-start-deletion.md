# Project deletion waits for starting runs and layout saves

Project deletion checked existing job status files but did not share the layout
locks used by simulation startup. Deletion could miss the interval between
loading inputs/marking a layout running and publishing pending status. Both HTTP
requests then succeeded, and the delayed pending write recreated a run directory
after its project metadata was removed. A paused layout save could similarly
recreate files after project deletion.

Deletion now holds the existing project tree lock, acquires all addressable
layout locks in stable filename order, and only then rechecks active jobs and
removes the project. The tree lock keeps new layouts from appearing during the
scan. Layout lock acquisition has a shared ten-second deadline; failure returns
503 before removal and releases locks already acquired. Filenames determine the
locks, so corrupt layout JSON does not prevent cleanup.

Focused verification:

- Before the fix: the first regression **failed**, 3.82 seconds. A starting
  simulation and deletion both returned 200.
- Related concurrency, deletion, image cleanup and API tests: **71 passed**,
  9.52 seconds.
- After adding pending-editor coverage and partial-lock-release checks, the
  focused boundary file: **12 passed**, 4.73 seconds. Final/preview runs are
  covered in both arrival orders: start wins → deletion 409; deletion wins →
  start 404 with no submitted job. Name and operations saves cannot recreate a
  deleted project. Busy/unrelated layouts, malformed JSON and invalid layout
  filenames are covered too.
- Strict type check of the changed application module: **zero errors/warnings**.

Coordination applies to simulation starts and saves using the layout locks.
Tests use temporary projects and stub background execution, without live model
calls. Frontend source is unchanged; the release's full suite was not repeated.
