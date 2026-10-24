# Preserve price comparisons beside unmatched rival products

The matching prompt permits no counterpart for a rival product. A local model
using `ours: null` for that case failed the whole response, including valid
matches in other rows. The application then reported a matching failure and
lost those products' price comparisons and suggested attraction adjustment.

Normalize only a null counterpart to the existing empty-string representation
and clarify that convention in the prompt. Keep the rival name required,
non-string counterparts invalid, null top-level pair lists invalid, and the
existing conflicting-match and bounded-name validation unchanged.

Before the fix, 13 new cases failed and four strictness controls passed in
3.61 seconds. Scripted HTTP tests exercise both JSON modes, null/omitted/empty
counterparts and one or 79 unmatched rows beside a valid match. They verify
one request, normalized saved responses, cached repeats, legacy null cache
entries, exact match counts, a 0.5 price index and the 1.5 suggested pull factor.
An application test verifies that the valid aliases survive without a false
matching-failure note.

After the fix, 99 focused matching, name-boundary, price-arithmetic and persisted
pull-adjustment checks passed in 4.87 seconds. Full source Pyright reported zero
errors and warnings. Tests emitted 39 existing LiteLLM async logging cleanup
warnings. No native inference or paid model calls were used.
