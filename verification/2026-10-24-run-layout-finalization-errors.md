# Simulation completion requires persisted layout state

The background runner logged and swallowed errors while finalizing a layout,
then published the run as completed. A failed layout write or lock acquisition
left that layout running, blocking another final run until server recovery.

Finalization errors now enter the existing run-failure handler. It restores the
layout to draft, clears this run's provisional runId if the write had already
reached disk, and publishes failed status with the underlying error. Successful
runs and previews retain their existing behavior. Persistent filesystem failures
can still prevent rollback; this change does not claim to repair failed storage.

Offline verification:

- Three initial fault-injection cases reproduced false completed status before
  the fix: failure before writing, after writing, and a lock-timeout exception.
- The final lock case injects failure at FileLock acquisition. Each case checks
  failed status, restored draft state, cleared runId and a successful fresh start.
- 32 focused terminal-state, editor concurrency and run-history cases passed in
  9.18 seconds. They include successful/failed previews and completion-publication
  failures.
- Strict Pyright on simulation.py: zero errors. Simulations used the rule engine;
  no model services were called.
