# VLM plans disambiguate identical names by category

The entry resolver searched the whole catalog for exact names before using the named category.
With `Original` in both Milk and Snacks, a model asking for Milk/Original received candidates
from both. The seeded picker could execute a snacks purchase and record the wrong category,
even though the intended milk offer was available. Repeated placements of one SKU also lost
the category's intended price/location.

Exact matches now search the resolved named category first. When there is no exact match
there, the existing catalog-wide exact-name fallback remains. This is a narrow ambiguity
correction; fuzzy/category/demand fallback policy is otherwise unchanged. The module description
was corrected to describe category preference rather than claiming an unconditional category fence.

- Baseline: 32 failed, 11 passed in 0.81 seconds.
- After: 129 passed in 16.74 seconds across the new ambiguity cases, existing VLM planning,
  plan votes and automatic-fill budgets.
- New cases cover Unicode/casefolded and one-character names, distinct/repeated SKUs,
  reversed catalog order, six shopper seeds, exact global fallback, fake VLM entry decisions,
  and executed rack/price/height attribution.
- Strict Pyright for `vlm_glance/planning.py`: zero errors/warnings.
- No live model calls, frontend changes or full suite.
