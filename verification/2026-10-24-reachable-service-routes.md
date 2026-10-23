# Reach checkout and departure from the shopper's own connected area

Layout validation floods from all entrances. A store with separately connected customer areas can
therefore pass validation even though one shopper cannot use every counter or exit. Routing chose
a walkable checkout stance and the first exit without checking connectivity. Empty paths then
became payment or departure events at the preceding shopping stop.

Checkout routing now tries the selected stance, other stances at that counter, and then other
counters. The resolved destination follows the successful path. Departure tries all declared exit
tiles, retaining entrance fallback for stores without declared exits. If no valid route exists,
execution raises an explicit error; the simulator's existing failure/retry handling excludes that
visit from revenue and shared-stock processing instead of fabricating a completed trip.

Focused offline evidence:

- **68 failures in 0.76s** before repair. Every test layout passes existing error-level validation.
  Cases cover two separate counters and a counter spanning a partition, both entrance areas,
  transposed layouts, diagonal/cardinal routing, and local/remote/body/missing checkout targets.
- Related routing, model-action, impulse-checkout, offer and quantity tests:
  **618 passed in 3.50s**. Changed routing module strict Pyright: **0 errors**.
- Four additional no-reachable-exit cases, plus the boundary matrix:
  **72 passed in 0.44s**. Reachable trips preserve exact valid checkout targets, contain no position
  jumps, and end at a reachable declared exit. Impossible checkout/exit routes raise clear errors.

No model calls, full suite, frontend or release changes. Entrance selection and layout validation's
multi-source reachability policy are unchanged. Explicit payment requests without any reachable
counter now fail; engines that generate no payment action are unaffected by that rule.
