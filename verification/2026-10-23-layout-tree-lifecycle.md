# New layouts cannot outlive deletion of their parent tree

A combined-photo save could pause before its new layout file was written, while
parent deletion scanned and removed the existing tree. The save then completed
with a parent ID that no longer existed. Per-layout locks could not protect a
child that was not in the deletion scan yet.

New layout commits and parent-tree/project deletion now share a project-scoped
tree lock outside the project directory. Creation checks project and parent
existence again under that lock. If creation commits first, deletion includes
the new descendant; if deletion finishes first, the prepared save returns 404
without writing its layout or acceptance receipt. Lock contention returns a
retryable 503 and does not block unrelated projects.

The guard covers empty/copied layouts, templates and buildings, floor-plan
imports, product edits, shelf reuse, starter products, library photos, text
edits, individual/combined captures and optimization application. Existing
layout locks still protect edits and running-state checks. Expensive preparation
usually stays outside the tree lock. Capture-batch saves acquire the tree lock
before their feature and layout locks to preserve deletion lock order.

Focused offline verification:

- Before the fix: the parent-deletion/capture-save reproduction failed
  (**1 failed**, 3.39 seconds).
- Initial capture, deletion, creation and project-image regressions:
  **63 passed**, 8.48 seconds.
- Final affected-path checks, including replay/interrupted writes, linked
  building rollback, template reuse, floor-plan import and optimization:
  **79 passed**, 9.93 seconds; 280 unrelated cases deselected.
- Eleven new cases cover both deletion orders, parent versus project deletion,
  empty/racks/full copies, acceptance receipts and project lock isolation.
- Strict backend types: **zero errors/warnings**.

This coordinates new layout commits; it does not make every background job,
existing-layout edit or auxiliary asset write transactional with project
deletion. No live model calls or real project data were used. Frontend source is
unchanged. Full suites were not repeated under the user's focused-validation
policy.
