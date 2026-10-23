# Choose reachable offers before building the basket

The shared rule/vision planner treated any walkable shelf stance as reachable, even
across a fully disconnected customer area. Its catalog also contained those offers.
A remote cheap/promoted copy of a locally available SKU could therefore win selection,
reserve the SKU and budget, and then be dropped by routing. Receipt-sized basket fill
and impulse stops had the same local-stance check.

The planner now caches the walkable component of its selected entrance and uses it
both to filter catalog offers and to validate planned/impulse stops. Cardinal
connectivity covers the supported diagonal paths because they cannot cut blocked
corners. The cache follows store identity and is cleared at run preparation, including
when a caller edits and reuses the same Store object. No per-shopper path searches are
added to candidate selection.

Exploration used seed **2610231917**, fake VLM replies and 160 valid disconnected
layouts. It combines entrance side, diagonal movement, multiple faces/heights for the
same SKU, different and zero prices, budget tolerances, quantity limits, receipt size,
missing product names, fractional walking speed and near-midnight arrival:

- Before: **118 cases** had planned purchases dropped by routing, in **3.315 seconds**.
- After: **0 findings**, in **3.134 seconds**. Checks also cover placement identity,
  hard spend limits, time ordering and continuous paths. This is bounded exploration,
  not a guarantee for every possible layout.
- Targeted baseline regressions: **39 failed in 1.44 seconds**.
- Related planning, fill-budget, selected-offer, category and zero-weight tests:
  **188 passed in 18.15 seconds**.
- Final cache handling checks passed. One test insertion initially placed assertions
  in the wrong test; after restoring them, **2 passed in 0.38 seconds**. The final new
  regression file contains **40 distinct passing cases**.
- Strict Pyright for the changed engine module: **0 errors**. No live model calls.

Artifacts: `/workspace/scratch/explore_vlm_disconnected_offers.py`,
`vlm-disconnected-offers-before.json`, `vlm-disconnected-offers.json` and
`reachable-offers-{before,after,final,cache,types-final}.log` in that scratch directory.
