# Ambiguous POS shelf attribution

The rack/category proxy assigned every SKU to the last rack containing it. With
chips on racks A and B, simulated nuts sales on A and real chips sales, reversing
the rack list changed rack Spearman from -1 to +1 and rack JS similarity from 0 to
1. Neither the physical layout nor the sales evidence had changed.

The report now detects sold SKUs in multiple rack/category groups and makes both
rack metrics unavailable, explaining that POS receipts lack the selling shelf.
SKU and basket comparisons remain available. Repeated offers within one rack,
racks sharing the same category label and unsold shared SKUs do not invalidate
the rack metrics. Existing negative-net-sales behavior is retained.

## Verification

- All six orderings of two product racks and a counter, with ambiguous sales in
  real data, simulated data or both, including POS returns.
- Same-label racks, unsold shared SKUs and repeated offers within one rack retain
  defined scores; unrelated SKU and basket metrics remain present.
- Baseline: 30 failed, 3 passed in 0.45 seconds.
- Focused new, analysis, returns and ranking tests: 392 passed in 1.19 seconds.
- Pyright for the changed source module: zero errors or warnings.

The report does not infer a shelf allocation from facings or simulated purchases:
neither establishes where the real receipt's product was picked up.
