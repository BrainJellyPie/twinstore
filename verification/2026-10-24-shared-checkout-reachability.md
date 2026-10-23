# Checkout capacity respects disconnected customer areas

The route builder already required a reachable checkout, but the shared-store replay then
assigned every paying shopper to the earliest free counter anywhere in the layout. In a valid
two-entrance floor split by a wall, three simultaneous local shoppers used the remote counter
and waited 0/0/60 seconds instead of 0/60/120. With 90-second patience, this also hid a customer's
abandonment and its lost sale.

Replay now computes connected walkable areas for the recorded queue positions and restricts
each checkout to counters with a service tile in that area. The geometry scan happens once per
replay, without a persistent cache. Cardinal connectivity also covers the route finder's diagonal
mode because it does not cut blocked corners. Existing staff schedules and per-counter busy
times still govern eligible counters. A counter accessible from both sides keeps one capacity.

Historical payments with blocked/out-of-grid positions cannot establish an area reliably and
retain the old pooled queue. This change does not reroute shoppers between reachable counters
or turn the aggregate till-count recommendation into a placement recommendation.

- Before: 24 failed, 4 passed in 0.46 seconds.
- Initial geometry fix: 28 passed in 0.39 seconds.
- Final: 774 passed in 28.04 seconds across checkout boundary cases, shared-store replay/API,
  customer memory, roster constraints and reachable service routes.
- New cases vary transposition, customer side, counter ordering, independent tills/crew/roster,
  shared counter access, connected versus divided floors, abandonment/revenue, and an accessible
  counter staffed only in the following hour.
- Strict Pyright for `simulation/shared_store.py`: zero errors/warnings.
- No live models, frontend changes or full backend suite.
