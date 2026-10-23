# Physical offers in shared-store stock substitutions

The shared-store pass pooled stock by rack, side and SKU, then used the first
stored item as a substitute's offer. For a multi-block rack this could replace a
sold-out purchase with a product on a different block, without moving the
shopper. A two-block reproduction recorded 350 in revenue while the existing
purchase invariant reported `sku_not_on_face`.

When a SKU appeared on multiple blocks or levels at different prices, the same
shortcut also selected the wrong name/price and checked the hard budget against
that unrelated offer. It could miss a free or affordable local offer, or record
an unaffordable local product at another block's cheaper price.

Stock records now index their offers by the physical shopper position. A
substitution selects an unlocked, valid offer at the current position, uses its
price for ranking, units and the remaining budget, and records its block/level.
The replay still uses its existing route and pooled inventory accounting.

Focused offline verification:

- **26 original-code failures in 0.41 seconds**: all four rack sides, direct and
  serialized visits, a replacement on another block, local/remote prices and
  names, free items, limited/unlimited budgets and multiple shelf levels.
- New cases, existing substitution-budget cases and shared-store inventory,
  refill, queue, return and planning checks: **615 passed in 8.12 seconds**.
- Strict Pyright for `engine/simulation/shared_store.py`: **0 errors**.

No paid model calls, full suite or frontend build were repeated.
