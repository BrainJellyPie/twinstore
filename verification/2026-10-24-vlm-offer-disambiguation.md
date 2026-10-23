# Preserve the numbered shelf offer through VLM resolution and votes

The name matcher chose the first best word match, even when several offers tied and the answer
contained a correct badge for another offer. A complete scripted VLM visit therefore selected a
700-minor-unit offer but bought the first 100-unit offer instead. Ensemble aggregation separately
reset a winning SKU to its first placement, even when every member selected its other placement.

Resolution now prefers exact printed names, retains all equally good candidates and uses the
badge to disambiguate them. Ambiguous distinct SKUs without a usable badge are unresolved;
name-only answers for repeated placements of one known SKU remain supported. At the response
text limit, prefix matches remain candidates because truncation can make a longer product's
name identical to another product's complete name. Exact short/Unicode/punctuated names work too.

Votes still choose the winning SKU by supporter count and summed interest. Within that SKU,
they keep the most-supported placement (ties use summed interest, then the lower badge number),
preserving its price, block and level through the existing purchase resolver.

Focused offline evidence:

- Duplicate names/SKUs, shuffled badges, fuzzy or truncated names, unanimous placement votes,
  and complete single-model/ensemble purchases: **17 failed, 1 passed in 0.66s** before repair.
- Related glance, ensemble and selected-block purchase regressions:
  **254 passed in 29.74s** after the initial repair.
- Two additional clipped-prefix collisions failed in **0.42s** before the prefix correction;
  final affected resolution/rendering and new purchase checks: **27 passed in 0.80s**.
- Changed prompt/resolver module strict Pyright: **0 errors**.

All providers were scripted fakes. No full suite, live model calls, frontend or release changes.
