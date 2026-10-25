# Do not match unusable capture labels to existing SKU identities

Shelf-photo matching indexed empty normalized catalog names. A model label such
as ??? or an em dash normalized to the same empty key and could acquire an
unrelated existing SKU and its stored price. An explicitly cleared label could
also match the generic Unknown product display fallback. Exact and fuzzy
matching both had affected paths.

The matcher now excludes empty normalized catalog names and requires usable
name or brand text from a labeled capture item. It preserves the captured item
when that identifying text is absent; it does not invent a match or replace its
price. Valid neighboring products continue through the usual unique/ambiguous
and estimated-price rules. This change does not reinterpret the captured label
or alter catalog entries.

Twenty-four actual LiteLLM/Instructor HTTP cases exercise punctuation-only model
labels, blank and punctuation-only catalog names, both JSON modes and exact/fuzzy
matching. They build captured items and verify that the unknown item's SKU and
price survive while a recognized neighbor retains its existing SKU and printed
price. Ten direct controls cover cleared labels, Unicode whitespace, the generic
display fallback and all-blank catalogs. Inputs remain unchanged and repeated
model reads use the cache. All 34 new cases failed before the fix in 2.94 seconds.

The focused identity, ambiguous-matching, optional-metadata and printed-price
suite passed 152 tests in 3.37 seconds. Full source Pyright reported zero errors
and warnings. There were 24 known LiteLLM asynchronous logging cleanup warnings.
The HTTP replies are scripted; no native inference, downloads or paid calls ran.
