# Preserve the distinction between planned and resolved purchases

Operations replay chose `timeline_planned.json` only when `operations.json` existed.
Deleting the report from a shared-stock run made replay use `timeline.json` as if
each shopper had originally shopped alone. A customer who wanted 300 minor units of
stock but lost the entire purchase to a stockout was then replayed as having no
demand, even when the new plan restored stock.

The loader now reads the saved configuration first. If that configuration declares
operations, or the run retains a planned timeline, a missing operations report is
reported as damaged source data (422) before replay or plan search starts. Configuration
JSON must also be an object. Genuine unshared runs, including older configurations
without an operations field, retain their existing replay path. Intact legacy shared
runs continue to use the report and planned visits.

- After fixing the reproduction fixture's stock-override field, the baseline had
  **10 failed, 4 passed in 2.94 seconds**. Missing-report cases reproduced zero planned
  revenue, and malformed configuration scalars/lists were incorrectly accepted.
- Focused final checks: **30 passed, 49 deselected in 9.53 seconds**. Coverage includes
  replay and plan gates, either source marker, missing planned visits, intact shared
  and unshared sources, earlier damaged-visit handling and legacy crowding defaults.
- Strict Pyright for the changed application module: **0 errors**.
- No live model calls; incomplete-source tests verify that saved files are unchanged
  and plan search is not invoked.

Logs: `/workspace/scratch/replay-source-{before,after,types}.log`.
