# Customer edits agree with the population a final run locks

A customer save checked for running/finalized layouts before writing, without
sharing the locks used by simulation startup. A save already accepted could
pause while a final run captured the old population and marked itself running;
the save then replaced the project's customers. The reverse race allowed an
edit after a run had captured inputs but before it published running state.

Customer saves now use the project-wide layout transaction already needed for
project deletion. The shared context holds the tree lock and all addressable
layout locks before checking restrictions and writing customers/metadata. This
keeps input capture and customer writes ordered without serializing unrelated
run starts. The HTTP handler uses the thread pool and preserves application
status codes, including retryable 503 lock timeouts and 404 missing projects.

Focused verification:

- Before repair: the first regression **failed**, 3.20 seconds. Both requests
  succeeded, but the submitted run held the old customer while the project held
  the newly saved customer.
- Related concurrency, project existence/deletion, image cleanup and API tests:
  **74 passed**, 9.80 seconds. Health responds while customer saving waits on a
  real layout lock; existing deletion safeguards and run-ID isolation pass.
- After adding empty-population boundaries, customer/start checks:
  **10 passed**, 5.45 seconds. Save first → the run receives the saved customers,
  or rejects an empty population without submitting a job. Final run first →
  the edit returns 409 and keeps its population. Preview runs keep their existing
  editable behavior after capturing inputs. Busy/unrelated locks are covered.
- Strict type checks of the three changed modules: **zero errors/warnings**.

Tests use temporary projects and stub background execution. No live models or
real user data were used. Frontend source is unchanged; validation remains focused.
