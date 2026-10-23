# Simulation transitions share the editor's setup lock

An editor save could read a draft layout, pause, then overwrite the running state
written by a new simulation. The run was pending while its layout said draft,
allowing the normal duplicate-run guard to be bypassed. Finishing a run could
likewise lose its locked/draft transition or overwrite newly saved operations.
A concurrent store edit could also leave the run using a different input snapshot
from the layout it marked running.

Simulation preparation now uses the existing per-layout file lock through
validation, input capture and the pending/running transition. Completion and
failure updates use the same lock around their fresh read and write. The lock
path helper is shared with editor and operations saves; unrelated layout lock
paths remain distinct. A start that times out acquiring the lock returns 503
before queuing work. Background transition write failures retain the run output
and are logged, instead of silently disappearing.

Validation:

- The original reproduction left **setup=draft / run=pending** after a concurrent
  name save. The initial race matrix had **10 failures / 2 passes**, 4.13 s.
- Initial race, lock isolation, recovery, currency and schedule checks:
  **29 passed**, 9.11 s.
- Extended checks: **53 passed**, 9.23 s. The 19 new cases cover both write orders,
  preview/final starts, successful/failed runs, name/memo/store/operations saves,
  busy-layout API errors without job submission and unrelated lock isolation.
- Strict backend types: **zero errors/warnings**. App import: **OK, 235 routes**
  without the built frontend's two static routes.
- Frontend source is unchanged from the verified snapshot: 4,479 tests, build
  and lint passed for that exact frontend source.

Full backend verification will be recorded before publication. Concurrency tests
use disposable data, controlled thread events and the offline rule-based engine;
no live model calls or real project data are involved.
