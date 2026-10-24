# Preserve product identity after entry-plan text bounds

The vision entry planner caps product names at 48 characters for local JSON
grammars. Providers without enforced bounds are normalized to the same length.
The resolver previously tried exact and word matches on that clipped value.
Long Korean/Chinese names and unspaced Latin labels could lose all word overlap:
with a category they became a random category choice, and without one they could
be unresolved. A scripted plan for two 700-unit products could instead purchase
two unrelated 100-unit products from the same category.

The resolver now considers literal prefixes only when the model field reaches
its existing 48-character bound. It searches the named category before the whole
catalog. All matching offers remain candidates, including a shorter exact name
that shares the prefix with a longer product. The trace distinguishes `prefix`
resolution from `exact`; short partial names, blank values and ordinary fuzzy
matching keep their previous behavior. No output bounds, budgets or seeded
candidate-selection rules change.

Before the fix, 37 regressions failed and seven controls passed. The final focused
run passed 146 tests in 1.32 seconds, covering multilingual names, repeated SKUs
with different offer prices, catalog ordering, actual quantity/revenue, missing
and unknown categories, strict JSON for full and grammar-clipped values, shared
prefixes and category disambiguation. Four existing planning/matching/vote controls
also passed. Strict Pyright reported zero errors. All model responses were scripted;
no live or paid inference was used.
