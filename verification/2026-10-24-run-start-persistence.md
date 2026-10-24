# Roll back rejected run registration

Simulation preparation marked the layout running and copied vision inputs before
persisting pending status. A failure during the layout or status write returned
an error without queueing any worker, but left running layout state, pending
status or image snapshots behind. The layout and run ID could then block retries;
an abandoned pending status also blocked project deletion.

Preparation now keeps the original layout until registration succeeds. Under
the existing layout/run locks, a failed request restores it (including its prior
timestamp) and removes the directory created for that request. Existing run-ID
and layout-state checks happen before the cleanup region, preserving history.
Snapshot failures use the same cleanup. Persistent storage failures are logged
if they also prevent rollback; the original exception remains visible.

Offline verification:

- 12 fault-injection cases combine rule/vision execution, preview/final runs and
  failures before/after writing status or layout state. Ten failed before the
  fix. Each now verifies no worker was queued, preserved layout, removed partial
  run directory and a successful retry using the same run ID.
- 59 registration, image snapshot, layout concurrency and terminal-state checks
  passed in 31.26 seconds.
- 32 project/run-ID reservation cases passed in 22.83 seconds, including
  simultaneous requests across layouts and projects and preview combinations.
- Strict Pyright on simulation.py: zero errors. Background workers were mocked
  or ran the offline rule engine; no model services were called.
