# Optimization application and project deletion

Applying an optimization saved the new layout under the project tree lock but
wrote `applied_setup_id` after releasing it. A concurrent project deletion could
finish in that interval; the late status write then recreated the deleted project
directory with an orphan optimization status.

The apply operation now holds the existing tree lock from reading the saved
result through writing the layout, active-layout state and optimization status.
Deletion that starts first returns a missing-project response to apply; deletion
that starts later waits until the complete apply operation finishes. This does
not add a lock around the optimization search or any model call, and does not
claim crash-atomic writes across multiple files.

Reproduction and verification (temporary projects, no provider calls):

- Seven new lifecycle cases cover deletion during layout/status writes, deletion
  first, default/custom result names and a busy tree lock. The original code
  failed both status-write cases. An explicit follow-up reproduction confirmed
  the project directory was recreated after deletion (2 failures, 3.26 seconds).
- The seven cases plus existing missing-source and building/operations apply
  checks passed: **11 passed in 4.98 seconds**.
- Strict Pyright for `application/optimize.py`: **0 errors**.

Only these focused checks were run for this change; no full suite or frontend
build was repeated.
