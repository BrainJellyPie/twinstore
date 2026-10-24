# Resolve bounded edit names without guessing targets

The product editor permits 200-character names, but automatic edit responses
limit products to 120 characters and shelves/packages to 80. Local constrained
decoding could therefore return a valid prefix that failed target resolution.
An existing shorter name equal to that prefix could instead select another
product, shelf or image.

At exactly the model field's limit, resolve all listed names beginning with the
copied text and accept only one underlying identity. Include an exact boundary
name in that ambiguity check. Shorter names retain exact matching; arbitrary
short abbreviations remain invalid. Multiple names for one identity are safe.
Both layout and A/B prompts explain the bounded-prefix convention. The existing
applicability validator and correction budget handle unresolved targets.

Before the fix, 26 cases failed and six controls passed in 4.45 seconds.
Scripted HTTP covers both JSON modes, layout and A/B drafts, Latin and Unicode
names, prices, placement and package changes, source immutability and cache
reuse. Controls cover two long names with one prefix, an exact name at the
boundary, distinct identities, aliases for the same identity and too-short
prefixes. A local boundary probe also confirmed 119/120-character names worked
while 121/200-character model prefixes failed before the fix.

After the fix, 215 focused edit and API checks passed in 8.06 seconds. Full
source Pyright reported zero errors and warnings. The 66 pytest warnings are
existing LiteLLM async logging cleanup warnings. No native model inference was
used.
