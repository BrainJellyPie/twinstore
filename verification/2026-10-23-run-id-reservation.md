# Concurrent layouts reserve separate run records

The layout lock prevented two final runs on one layout, but run IDs belong to
the whole project. Two different layouts could both pass the ID checks before
either pending status was written. Both requests were accepted and launched jobs
that wrote into the same results directory; both layouts could become running.

The final duplicate check, layout transition and pending status write now hold
a project/run-specific file lock, in addition to the existing layout lock. The
losing request returns 409 before changing its layout or submitting a job.
Different projects and different run IDs have separate locks.

Focused verification:

- Before the fix: the first regression **failed**, 3.01 seconds; both HTTP
  requests received 200 for the same project/run ID on different layouts.
- After the fix: **50 passed**, 11.77 seconds, including 16 new cases covering
  all final/preview combinations, explicit and generated ID collisions, and
  independent projects/IDs. Only one job is submitted for a collision; its
  status retains the correct layout and the rejected layout remains draft.
  Existing editor/start races, API responsiveness and restart recovery pass.
- Backend strict type check: **zero errors/warnings**.

The API still returns 409 on a duplicate generated ID, as before. Tests use
temporary data and stub background execution; no live models are called.
Frontend code is unchanged; full suites were not repeated for this fix.
