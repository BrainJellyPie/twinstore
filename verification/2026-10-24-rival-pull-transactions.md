# Coordinate rival pull changes with their saved baselines

Rival comparisons saved the town under its locks, then wrote the separate reapplication baseline
after releasing them. Another apply could compound the first adjustment or overwrite a different
venue's baseline; project deletion between the writes could be followed by an orphaned directory
being recreated. These baselines affect future neighborhood demand calculations.

Town writing now exposes a scoped, validated writer while retaining the project and town locks.
Normal saves use the same path and retain expected-town conflict checks. Rival applications read
the current town and baselines inside that boundary, then write both before releasing it. Model
matching and comparison remain outside the critical section. A baseline OSError triggers a town
rollback while the locks are still held.

Focused offline evidence:

- Deterministic overlapping HTTP applies (same and different venues), deletion between writes
  and deletion first: **3 failed, 1 passed in 3.96s** before repair.
- Rival apply, town lifecycle/conflicts/integrity/numeric checks: **57 passed in 9.84s**.
- Injected first/replacement baseline-write failures exposed two partial commits after the locking
  repair (**2 failed, 1 passed in 3.27s**, selected checks); rollback now preserves the old town and
  baseline and permits a normal retry. Final affected tests: **7 passed in 4.14s**.
- Changed town and Shelf Lab modules strict Pyright: **0 errors**.

This coordinates live requests and handles baseline I/O errors when the town rollback remains
writable. It is not a crash-atomic transaction across both files. No live model calls, full suite,
frontend or release changes.
