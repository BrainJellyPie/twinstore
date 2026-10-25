# Recover unambiguous starter identifier spelling variants

Automatic starter selection treated `HOME_COFFEE_TEA`, a padded catalog ID and
upper-case catalog SKUs as unknown choices even when they uniquely named an
offered entry. Repeating those spellings also exhausted the smaller recovery
tasks, preventing an otherwise valid assortment from reaching placement. Rack
ID case changes unnecessarily triggered positional recovery.

Normalize known identifiers in the task-specific response validators before
caching. Preserve an exact match first, then a trimmed exact match, then one
unique case-folded match. Leave unknown and ambiguous values for the existing
validation and bounded recovery. This applies to primary categories/racks,
category-scoped product SKUs and smaller category/product choice tasks. The
transmitted grammar still enumerates the original exact identifiers.

Case-distinct racks remain separate. An ambiguous `CASE` cannot choose between
`Case` and `case`; the existing positional recovery can still address both
without guessing their IDs. Literal whitespace in an exact supplied ID is also
preserved. Normalization does not deduplicate repeated SKU selections or allow
products from another category.

Thirty-two real LiteLLM/Instructor HTTP cases cover both structured modes,
primary and smaller tasks, category/rack/SKU/combined variants, uppercase and
Unicode surrounding whitespace. They verify exact catalog placement in a KRW
store, an unchanged source layout and repeated cache use. Before the fix,
28 tests failed and six passed in 3.82 seconds, including two case-collision
controls: most failures exhausted selection, while primary rack-only variants
exposed unnecessary extra requests.

The focused selection, grammar, correction, category-limit and context-recovery
suite passed 190 tests in 6.31 seconds. Two additional boundary checks verified
that normalization cannot hide duplicate SKUs or merge exact whitespace IDs
(2.07 seconds). Thus 192 distinct relevant checks passed. Full source Pyright
reported zero errors and warnings. No native inference, model downloads or paid
requests ran; HTTP replies are scripted to exercise the selection harness.
