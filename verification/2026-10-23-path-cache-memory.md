# Bound route-cache memory for large maps and repeated layout searches

The cache limited itself to 200,000 entries, each retaining a separate tuple copy of the full walkable
map. On a 64×64 map, 100 distinct two-tile routes retained **3,588,000 bytes of map tuples alone**
(35,880 per entry), despite all maps being identical. At the old entry limit those key tuples alone
would account for about 7.2 GB; that maximum was not allocated during investigation.

Add a 64 MiB accounted cache budget per pathfinder. Count grid/path tuple sizes and conservative entry
overhead, evict least-recently-used entries until both limits hold, and leave oversized entries uncached.
Concurrent insertions of the same key replace their accounting rather than double-counting it. The
algorithm, exact full-map keys, changed-map sensitivity and returned-list copies remain intact.

Focused evidence:

- Square, wide and tall maps with orthogonal/diagonal routing, forced small memory budgets, oversized
  entries, changed obstacles, concurrent insertions and mutation of returned paths.
- Measure retained Python objects and verify every route again after eviction.
- Before the fix: **8 failed in 1.45s**.
- New cases plus routing, perception/routing and calibration modules: **194 passed in 2.72s**.
- Strict Pyright on the changed module: **0 errors**.

The budget accounts for retained cache objects, not total process RSS or temporary A* search allocations.
Large searches may recompute evicted routes. No live model calls, full suite, frontend or release binary changes.
