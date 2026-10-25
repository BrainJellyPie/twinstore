# Preserve distinct shelf categories during online import

The physical-store importer made category IDs by removing punctuation and keeping
only 40 characters of a shelf sign. Different emoji signs, punctuation and long
shared prefixes therefore collapsed into one category, misclassifying products.

Map full lowercased shelf labels to unique sequential import IDs, as product IDs
already are. Preserve the first display label, case-insensitive repeated signs
and the existing removal of running shelf numbers. This affects newly imported
sites only; saved site identities and source layouts remain unchanged.

Nine regressions cover punctuation, emoji, long English/Korean/Chinese/Japanese
labels, exact repeats, numbered repeats, case variants, deterministic imports and
source preservation. Before repair: six failed and three passed in 0.24 seconds.
After repair: 43 focused import and online API tests passed in 7.35 seconds.
Full-source Pyright reported zero errors and warnings; backend boot passed.
No frontend source, paid inference or downloaded weights changed.
