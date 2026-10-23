# Align planning summaries with retained purchases

Items excluded by the trip's category-breadth limit retained their resolved SKU, so planning
summaries incorrectly counted them as bought. Automatically filled purchases had the opposite
problem in category rankings: their records omitted the category. A four-item plan could report
six purchases, and after removing the rejected items its category counts still summed to two.

Summaries now exclude breadth-rejected items from purchases. Fill records obtain the category
from the chosen shelf placement (target, face, SKU, block and level), retaining distinctions when
a SKU appears in several categories. Resolution diagnostics still retain rejected-item reasons.

Offline evidence:

- Seed **24102471**, **200** combinations of budgets, tolerances, basket sizes/breadths, item
  quantities, free/paid goods and model plans: **35** purchase-summary mismatches in **3.769s**.
  Budget, executed purchase counts, quantity limits and revenue checks found no other mismatch.
- Two existing complete plan tests gained summary assertions: **2 failed in 0.66s** before repair.
  After excluding rejected items, a category-total assertion exposed missing fill categories.
- Focused plan/summary/fill checks: **30 passed in 1.18s**. Changed engine strict Pyright: **0 errors**.
- Repeated 200-case exploration, also checking category totals: **0 findings in 3.910s**.

The exploration and reports are saved under `/workspace/scratch/explore_vlm_plan_invariants.py`
and `vlm-plan-invariants-{before,after,final}.json` in the working environment. No live model calls,
full suite, frontend or release changes. Existing saved reports are not rewritten.
