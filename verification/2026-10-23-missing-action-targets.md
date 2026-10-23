# Missing action coordinates still require a physical visit

Model actions allow an omitted target. A BUY with a valid SKU passed the
hallucination guard, but routing returned early before resolving its shelf.
The timeline then priced the purchase while the shopper remained at the
entrance. A PAY without a target likewise took place without visiting a counter.

Known-SKU and checkout destination resolution now run before the generic
missing-target return. A product uses the existing placement resolver; checkout
uses an available service tile. Explicit destinations retain their existing
behavior. Unknown SKUs still fail the existing guard, and their orphaned PAY
actions are removed.

Focused offline verification:

- Before the fix: **12 failed / 5 passed**, 0.40 seconds.
- After the fix: **191 passed**, 0.80 seconds across routing, selected offers
  and model purchase-quantity/budget regressions.
- Seventeen new cases cover omitted/present purchase and checkout coordinates,
  orthogonal/diagonal routes, different shelf locations, repeated-SKU placement,
  physical reachability, counter attribution, quantity/pricing, input preservation
  and unknown-SKU rejection.
- Strict backend types: **zero errors/warnings**.

No live models or real project data were used. Frontend source is unchanged;
full suites were not repeated under the user's focused-validation policy.
