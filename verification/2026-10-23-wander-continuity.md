# Wandering follows the path used for the next stop

The route builder chose a wandering endpoint using estimated pauses, but the
timeline independently stopped walking when actual random pauses exhausted its
budget. The next route leg still started at the planned endpoint. A generated
compact convenience store reproduced a jump from (3, 6) to (1, 6), skipping the
intermediate tile. Diagonal steps also cost more time than the route's budget
calculation allowed, and glance timestamps marked their end rather than start.

The timeline now reserves the complete planned walking time before assigning
glances, then walks every planned tile. Glances use the remaining time and
record their start. Route preparation accounts for each step's actual length
and stops before a step that does not fit. This keeps subsequent paths anchored
to the shopper's actual position without changing the supplied journey.

Focused offline verification:

- Before the fix: **23 failed / 16 passed**, 0.51 seconds.
- After the fix: **134 passed**, 1.38 seconds across routing, movement maps,
  route heatmaps and selected-offer regressions.
- Thirty-nine new cases cover orthogonal/diagonal paths, multiple pause seeds,
  short/zero budgets, fractional walking speeds, exact path continuity,
  repeatability, input preservation and glance start/duration ordering.
- Strict backend types: **zero errors/warnings**.

No live models or real project data were used. Frontend source is unchanged;
full suites were not repeated under the user's focused-validation policy.
