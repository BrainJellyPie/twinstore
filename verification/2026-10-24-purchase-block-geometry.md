# Preserve the selected shelf block through purchases

Two blocks on the same shelf face can offer the same SKU at different prices. Placement lookup
previously accepted a stance belonging to any block on that face, and routing chose the first
walkable face tile. A purchase aimed at the 400-unit offer could buy the adjacent 100-unit offer,
or a rule-based decision could retain the 400-unit price while standing at the 100-unit block.

Face acceptance now optionally identifies a block. Placement resolution, BUY sanitization and
rule-based buying/browsing pass the selected slot's block. An obstructed selected stance does not
become another block's stance. Diagnostics identify the reached block from position and face,
checking only its offers and locks; older timelines without a usable stance retain face-level checks.

Focused offline evidence:

- New matrix: four faces, four rotations, both block selections, reversed slot order, and correct,
  missing or wrong face hints; blocked rule-based visits and block-specific diagnostics.
- Corrected-fixture baseline: **164 failed, 52 passed in 1.66s**. An earlier fixture-only failure
  omitted required rack shapes and is not counted as evidence of the product defect.
- After: **450 passed in 2.98s**, covering routing, selected offers, purchase quantities, LLM quantity
  handling and impulse checkout. Strict Pyright on all five changed source modules: **0 errors**.

No live model calls, full suite, frontend or release changes. Shared inventory's existing
rack/face/SKU pooling is unchanged. Broader unreachable-path execution is a separate investigation.
