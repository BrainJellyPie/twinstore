# POS ranking scores and tied simulated sales

NDCG sorted simulated unit counts stably and therefore broke ties by the input's
SKU ordering. For two SKUs with no simulated sales and real sales of 100 and 0,
NDCG@1 was 1.0 or 0.0 depending only on which SKU sorted first. Equal positive
predictions had the same problem.

The metric now averages relevance within each tied prediction group and applies
the sum of that group's rank discounts. A tie crossing the top-K boundary uses
all members of the tie, including those outside the cutoff. This equals the
average over every possible ordering within ties, without enumerating them.
The example above now scores 0.5 in either order. A nonzero tied-ranking score
does not by itself establish good calibration; the report's other distribution
and basket metrics still apply.

Focused offline verification:

- **22 failed, 21 passed in 0.74 seconds** on the original implementation.
- Independent exhaustive-permutation oracle for small rankings, ties before/at/
  across the cutoff, all-zero predictions, weighted-goods relevance, no relevant
  sales, oversized K and untied rankings. A seeded exploration of 80 rankings
  checks four cutoffs each against shuffled input order (seed 261023947).
- Integrated POS reports for zero and equal positive simulated sales, plus
  existing analysis and returns checks: **359 passed in 1.06 seconds**.
- Strict Pyright for `engine/analysis/fidelity.py`: **0 errors**.

No full suite, frontend build or provider calls were needed.
