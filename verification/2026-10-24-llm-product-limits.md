# Enforce LLM shopper purchase limits before execution

The three-stage LLM simulator only described `BehaviorPattern.max_products` in
its prompts. Valid catalog purchases above that limit still reached the timeline
and revenue totals, including purchases from a zero-purchase browsing pattern.
This differed from the purchase cap enforced by the rule-based shopper.

The engine now removes nonexistent planned purchases and applies the pattern's
effective purchase-line limit before constructing the exposure route. The impulse
prompt receives the bounded plan and its actual purchase count. After merging,
invalid-SKU and budget handling still run, then the same purchase cap prioritizes
planned products over impulse additions. Quantities on retained purchase lines
are unchanged. Payment is removed when no purchases remain. Original model
responses remain in the trace, alongside `dropped_product_limit`; invalid-SKU
and over-budget counts remain separate. No extra model requests are introduced.

Before: 40 failing execution/route cases and 28 passing controls. After: 120
focused product-cap, action-boundary, budget-quantity and offline-engine checks
passed in 0.69 seconds. Two additional shared-store checks passed in 0.33 seconds,
for 122 unique checks. They verify that zero-purchase customers create neither
revenue nor checkout traffic, and that a retained three-unit planned line keeps
its full value. Other cases cover limits 0/1/2/4, both route orderings, planned and
impulse purchases in different combinations, one/three units per line, unknown
SKUs, stage-three purchase counts, exposure-route pruning, exit/payment behavior,
trace preservation and unchanged source stores.

Strict Pyright reported zero errors and diff whitespace checks passed. Scripted
model responses feed the actual route builder, customer executor and shared-store
resolver. No weights, live inference or paid calls were used. This verifies the
declared purchase constraint, not the behavioral realism of model choices.
