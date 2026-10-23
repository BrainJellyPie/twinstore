# Selected shelf offers survive execution

The rule-based planner chose a concrete item and counted its price against the
shopper's budget, but its action retained only SKU and face. Execution looked up
the first matching shelf level again. A chosen 25-unit offer therefore became
a 100-unit purchase; a free item could become paid. This affected planned and
impulse purchases, including the planner used by vision-assisted shoppers.

Engine-selected actions now retain optional block/level hints through routing,
budget evaluation and timeline construction. The hints stay out of model
response schemas; legacy/model-generated actions without hints retain their
existing resolution behavior. Prices remain derived from the selected catalog
item rather than copied unchecked into actions.

Stockout loss and closest-price substitution now use the shopper's selected
price. Purchase diagnostics accept a matching name/price pair from any actual
offer on the face, rather than comparing only with the last stored level.

Focused offline verification:

- Initial chosen-offer reproduction: **6 failed**, 0.37 seconds.
- Initial purchase/budget/routing checks: **90 passed**, 1.11 seconds.
- Final routing, budget, quantity and shared-store checks: **641 passed**,
  6.30 seconds; strict backend types: **zero errors/warnings**.
- The 13 new cases cover either stored level, planned/impulse purchases,
  free/discounted/more expensive offers, full and partial stockouts, partial
  substitution, actual selected prices and hidden model-schema hints.

No live model calls or real project data were used. Frontend source is unchanged.
Full suites were not repeated under the user's focused-validation policy.
