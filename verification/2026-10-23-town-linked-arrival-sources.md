# Match linked visitor origins to their hour and age

Demand correctly respected venue opening hours, but arrival annotations drew source venues using
only their daily totals. In a town with morning and evening cafes, 14 of 20 linked visitors were
attributed to a closed cafe (seed 42). Those annotations feed shopper prompts and the affected
visitor panel in venue synergy comparisons.

Retain each source venue's hour/age flow in the demand report and use it for seeded source draws.
Filter source candidates by opening hours, including older reports without the new optional field.
When the persona pool lacks the requested age and substitutes another, fall back to the hour's
complete age mix if the substitute age has no source demand. Daily reported totals keep their meaning.

Focused evidence:

- 39 new cases cover disjoint/adjacent opening intervals, overnight hours, closing at midnight,
  equal opening/closing hours (24-hour operation), partial overlaps, three seeds, legacy reports,
  disjoint age/hour source populations, absent pool ages, report reordering and paired traffic changes.
- Before the fix: **38 failed, 1 passed in 3.03s**.
- New cases plus existing town generation/demand/visitor and offline VLM synergy checks:
  **153 passed in 14.24s**.
- Strict Pyright on the three changed modules: **0 errors**.

Older reports cannot recover hour/age weights they never stored; they retain daily weighting among
venues open at the arrival hour. New estimates include conditional weights. No live model requests,
full suite, frontend or release binary changes.
