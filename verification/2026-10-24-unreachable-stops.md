# Exclude point stops when their route fails

Purchase and checkout routes already checked reachability, but a disconnected BROWSE (including
an action with the implicit browse default) or MOVE still entered the timeline. It was recorded
at the previous position with the remote target's shelf and dwell, delaying the real visit and
feeding false shelf stops into shared-store crowding accounting.

Point actions with a destination now require the route's actual endpoint to reach that destination.
Skipped stops leave the customer's current position unchanged. Browsing without a destination
continues to mean looking around at the current position. Checkout/exit fallback behavior and
purchase-placement checks retain their existing semantics.

Focused offline evidence:

- Valid divided stores, both entrance sides, transposed layouts, cardinal/diagonal movement,
  explicit/implicit browsing and MOVE, shelf-body/access hints: **48 failed, 50 passed in 0.70s**
  before repair. Opening a doorway was the positive control.
- Blocked visits now exactly match the corresponding visit without the unreachable stop,
  including later paths, prices, dwell and departure; inputs remain unchanged.
- Routing, perception, offline model actions and shared-store regressions:
  **1,226 passed in 8.22s**. Changed route-builder strict Pyright: **0 errors**.

No live model calls, full suite, frontend or release changes.
