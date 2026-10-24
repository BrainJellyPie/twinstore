# Reachable prices in marketing experiments

The simulator removes inaccessible product slots from a private layout, but
the marketing report previously selected the lowest price from the original
layout. A hidden 100-minor-unit offer could become the baseline price of sales
made from the reachable 300-unit offer, distorting the demand curve and its
elasticity. A missing arm price also silently inherited the control price.

Price collection now applies the runner's existing slot-clearing operation to
a private copy. The established lowest-facing rule applies to the surviving
offers. Price-response points require that arm's own recorded price. Neither
the saved layout nor ordinary experiment sales and comparison metrics change.

Validation:

- Before the fix, 17 cases failed and four valid controls passed.
- The final 25 cases cover wall, locked, occupied, disconnected and occluded
  facings; zero and positive hidden prices; a surviving alternative versus no
  reachable offer; multiple accessible prices; missing arm/control prices; and
  preservation of the caller's layout.
- All 55 focused marketing, price-sweep and common-cohort tests passed in
  5.01 seconds, including the existing offline rule-engine price experiment.
- Strict Pyright passed for both changed production modules.

This retains the existing lowest-reachable-price convention when one SKU has
several accessible prices; it does not estimate transaction-weighted prices.
