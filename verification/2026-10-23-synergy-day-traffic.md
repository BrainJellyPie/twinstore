# Avoid duplicate day-type traffic in venue synergy studies

The area panel and ordinary neighborhood runs already omitted a weekend/holiday traffic factor when
the town demand profile represented that same day type. Basket-synergy studies applied the factor
again. A deterministic 200 m town with the heatwave-weekend preset produced 265.773 visitors in the
study calculation versus 279.761 with the area calculation (the extra default 0.95 weekend factor).
Daily revenue estimates inherit this visitor scale.

Move the existing area traffic helper into the engine town layer and share it with the study.
Keep the full scenario effects for customer budgets, baskets and situation prompts; only the
traffic calculation excludes an already represented day-type effect.

Focused evidence:

- 60 combinations: three demand profiles × five scenario day types × two store formats × default
  or custom priors, also including rain, a timed event, hourly multipliers and explicit traffic scale.
- Three completed fake-engine studies confirm that weekend/holiday budget and situation effects remain.
- Before the fix: **12 failed, 51 passed in 0.61s**.
- New cases plus existing neighborhood visitors, store-format synergy, API and day-profile checks:
  **82 passed in 10.98s**. Strict Pyright on four changed modules: **0 errors**.

Separate exploratory run after the preceding source-attribution fix: seed 1042386, 180 randomized
town combinations, 2,721 generated visitors, 0.333s, no violations of the inspected finite/nonnegative
demand, total decomposition, opening-hours, unique-ID or aligned annotation conditions.
Script/report are local scratch artifacts, not a claim of exhaustive coverage.

No live model requests, full suite, frontend or release binary changes.
