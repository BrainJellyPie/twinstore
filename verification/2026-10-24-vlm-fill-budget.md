# Preserve VLM spend limits during automatic trip filling

The VLM planner capped the model's explicit purchases, then filled a known-size trip within its
kept categories using the rule planner's soft-budget helper. Those extra purchases could exceed
the VLM cap by an arbitrary amount, especially when a costly usual product had high choice weight.

The fill helper now accepts an optional spend limit. VLM filling passes the same limit used for
explicit model purchases; item selection excludes unaffordable candidates and quantity assignment
fits the remaining amount before updating the plan. The rule planner retains its existing soft
budget behavior by leaving this option unset. Free goods, tolerance zero, disabled tolerance and
the existing zero-budget/unlimited convention keep their meanings.

Focused offline evidence:

- Four seeds across unaffordable-only and mixed alternatives, exact remaining prices, free goods,
  multi-unit draws, expensive usual products and unlimited plans: **20 failed, 9 passed in 0.98s**
  before repair. Results are checked after complete purchase execution.
- New boundaries, VLM planning, quantity limits, selected offers and choice weights:
  **117 passed in 17.15s**.
- Strict Pyright on the two changed engine modules: **0 errors**.

Scripted model answers only; no full suite, live providers, frontend or release changes.
