# Keep result analysis off the API event loop

Run comparison, POS fidelity and customer CSV export called synchronous parsing/calculation directly
from async routes. On this workspace, a 7,000-customer comparison with 2,000 bootstrap draws took 0.408s,
and parsing 4,000 POS rows (138,935 bytes) took 1.696s; the server event loop was unavailable for that work.

Dispatch these three existing services through the route's existing thread-pool facility. Preserve
uploaded bytes/filename, comparison arguments, response models, CSV BOM/download headers and errors.

Focused evidence:

- On a single production ASGI loop, hold each analysis in progress and request health concurrently.
  Health must finish before releasing the analysis; cover successful and missing-run responses.
- Preserve application error codes for comparison/fidelity and the full export body and headers.
- Before the fix: **6 failed, 2 passed in 9.40s** (health waits exceeded the 1s test deadline).
- New cases plus existing rewritten-customer/shared-store comparisons and CSV output checks:
  **98 passed in 3.51s**.
- Strict Pyright on the changed route module: **0 errors**.

This removes event-loop blocking; it does not speed up the underlying calculations or guarantee latency
under a saturated worker pool. No live model calls, full suite, frontend or release binary changes.
