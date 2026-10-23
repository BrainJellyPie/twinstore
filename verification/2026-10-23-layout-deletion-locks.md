# Layout deletion and pending saves

A save could read a child layout, pause while holding its file lock, then write
after deletion had removed the child and parent. The API reported successful
deletion but the child reappeared without its parent. This affected editor saves
and operations settings, on either the requested layout or a descendant.

Deletion now acquires every affected layout's existing file lock, in stable ID
order, before changing files. It rereads running states after acquiring the
locks and retains them through deletion and active-layout selection. A single
10-second acquisition budget applies across the tree. A busy layout returns
503 without partial deletion; unrelated layout locks do not block the request.

Validation used disposable data and no live model calls:

- Reproduction matrix before the fix: **8 failed, 1 passed**, 3.68 seconds.
- Focused deletion, creation, save-lock and simulation-state regressions:
  **33 passed**, 10.30 seconds. These cover parent/child editor and operations
  saves, lock contention, unrelated locks, lock release after errors, and a
  simulation starting while deletion waits.
- Strict backend types: **zero errors/warnings**.
- Frontend source is unchanged.

Per the user's request to spend roughly 90% of effort on discovery/fixes and 10%
on verification, the full backend/frontend suites were not repeated. This fix
coordinates saves and simulation transitions on existing layouts; concurrent
creation of new descendants by other workflows is outside this patch's scope.
