# Scenario traffic copies and optimization panels

Traffic expansion assigned unique IDs to extra visitors but left `twin_of` empty
when copying an original customer. The optimizer therefore treated those copies
as newly written profiles and sampled them before other available originals.

An offline reproduction with 20 distinct customers, a 5× traffic scenario and
seed 261023 produced 100 visitors with no copies marked. Its 20-person optimizer
panel represented only 14 distinct profiles, despite all 20 being available.

Extra scenario visitors now record their source's `twin_of` or its own ID. The
original visit keeps its existing reference. Repeated expansion and expansion of
daily-sample twins keep the original root. Visitor counts, IDs, budgets and
per-visitor randomness remain unchanged; the existing panel-selection policy
can now prioritize written profiles as intended. Panels larger than the number
of written profiles still include copies, and this change does not claim every
large panel is statistically independent.

Focused verification, without provider calls:

- 23 new cases: fractional/integer traffic, disabled traffic scaling, existing
  twins, reserved clone IDs, filtered days, budget scaling, repeated expansion,
  three seeds and panels from 1 through all 100 visitors. Baseline: **14 failed,
  9 passed in 0.35 seconds**.
- New cases plus existing clone-ID, reproducibility and budget-floor checks:
  **73 passed in 0.67 seconds**.
- Strict Pyright for `engine/scenario.py`: **0 errors**.

No full suite or frontend build was repeated.
