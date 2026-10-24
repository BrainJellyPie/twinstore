# Prevent clipped shelf-test names from selecting shorter targets

Shelf-test model fields allow 160-character product and image names. A longer
listed name clipped at that limit could match another shorter complete name
inside the prefix. The resulting study then targeted the wrong SKU or package.

At the field limit, check known name prefixes before exact-name or complete-word
matching. Accept only a common identity across those matches; ambiguous prefixes
do not fall through to a shorter target. When no known prefix exists, existing
complete-name/description handling remains available. Enable this behavior only
for the shelf-test fields and state the copying convention in their prompt.

Before the fix, 12 cases failed and two controls passed in 2.44 seconds.
Scripted HTTP tests cover both JSON modes, long Latin/Unicode names, a shorter
decoy name, exact target SKU/rack, price and package effects, cache reuse and
source immutability. Collision controls cover exact boundary names, distinct
long-name identities, same-identity aliases and preservation of a valid sign
when the package choice is ambiguous.

The focused shelf-test, name-resolution, automatic-edit and layout-brief suite
passed 126 checks in 3.82 seconds. Another 18 draft-recovery checks passed in
2.18 seconds, including bounded correction and no cache entry after repeated
ambiguous-target replies. Full source Pyright reported zero errors and warnings.
The 47 suite warnings are existing LiteLLM async logging cleanup warnings.
No native model inference was used.
