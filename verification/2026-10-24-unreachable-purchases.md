# Do not sell products the shopper cannot reach

An empty path previously left the shopper at the preceding stop while timeline execution still
created the requested purchase. Generic target snapping also let an obstructed shelf stance become
a different floor tile. Both paths could record sales and consume shared inventory without reaching
the product.

BUY sanitization now retains the selected block and level and leaves an unavailable stance
unavailable. Journey construction requires an actual endpoint on that offer's unlocked face before
including the purchase. Invalid visits do not change the next journey's starting position. Unknown
or empty SKUs are excluded and added to the existing invalid-SKU diagnostic; valid but unreachable
offers are logged separately so they are not mislabeled as hallucinated products.

Focused offline evidence:

- Baseline: **50 failed, 32 passed in 0.66s**. Matrix varies all four faces, cardinal/diagonal routing,
  explicit/omitted targets, a solid wall, an open doorway, a blocked stance, a locked face and an
  open aisle. Every trip includes a subsequent reachable purchase and checkout.
- Related routing, model-action, quantity, offer, impulse-checkout and perception checks:
  **568 passed in 3.20s**. Strict Pyright on both changed source modules: **0 errors**.
- Added shared-stock assertions then passed with the final invalid-SKU counting adjustment:
  **82 passed in 0.45s**. A sold-out inaccessible product creates neither lost units nor lost revenue;
  the same accessible product produces the expected three lost units and 1500 minor currency units.
  The executor's final type check also passed.

No live model calls, full suite, frontend or release changes. Low-level timeline rendering still
accepts prebuilt journeys; runtime decisions are validated during journey construction. Unreachable
checkout/exit handling remains a separate investigation.
