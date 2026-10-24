# Preserve full identities in bounded rival-product aliases

Both names in a model-produced rival alias were limited to 160 characters.
Longer names were silently dropped; if another product's full name equaled the
clipped prefix, the alias selected that product instead. This affected both
our-product targets and rival-product keys and could change the price index
and suggested venue pull.

At the output boundary, resolve a copied prefix only when one full listed name
matches. Preserve exact matching below the boundary and existing case handling.
Keep ambiguous pairs unmatched. The prompt explains the bounded copying rule.
Use the same resolution for conflict validation and returned aliases, retaining
the correction loop added for contradictory targets.

Before the fix, 20 cases failed and eight controls passed in 2.77 seconds.
Scripted HTTP covers both JSON modes, Latin and Korean catalog names, long names
on either or both sides, collisions with exact boundary names, a legitimate
exact boundary name, shorter incomplete prefixes and cached repeats. Assertions
check full alias identities, matched counts, exact price index and pull factor.

After the fix, 84 focused alias, conflict, comparison and rival-pull application
tests passed in 4.71 seconds. Full source Pyright reported zero errors and warnings.
No native model inference or paid model calls were used.
