# Preserve hard spending limits during stock substitutions

A VLM shopper with a 100-unit budget correctly planned a 100-unit purchase, but shared-stock
replay replaced the sold-out item with a 175-unit item. The planner's hard limit was absent
from its decision/result, so the replay could choose arbitrary replacement prices and units.

Hard VLM plans now carry an optional spend limit through their decision, execution result
and saved JSON. Replacement selection reserves every other remaining BUY line, including
future picks, and filters products and quantities against the available amount. Earlier
stock losses and replacements already appear in that timeline, so money released by them
can be used. Free replacements remain valid, including with a zero limit. Unfilled units
continue to count as lost demand at the originally requested price.

Rule planning retains its existing soft budget. Unlimited VLM settings and legacy saved
results without a recorded hard limit retain their former substitution policy; the missing
historical contract is not invented. This fix applies to newly produced hard VLM plans and
their subsequent saved replays.

- Direct reproduction: budget 100, planned spend 100, replay spend 175 before the fix.
- Baseline matrix: 28 failed, 17 passed in 1.71 seconds.
- New substitution cases plus VLM fill budgets: 74 passed in 1.94 seconds.
- Strict Pyright for all six changed source modules: zero errors/warnings.
- Seeded exploration 24102494: 100 combinations, 441 shoppers, 8.052 seconds, zero budget,
  planned-versus-lost unit or finite-stock conservation findings.
- Related shared-store, LLM budget, VLM planning, customer memory and shared-store API tests:
  688 passed in 40.10 seconds. No full backend/frontend suite or provider calls.
- Boundary coverage includes free original/replacement items, zero/fractional/above-one
  tolerance, unaffordable replacements, capped quantities, future reserved purchases,
  unlimited settings, input immutability, JSON replay and legacy results.
