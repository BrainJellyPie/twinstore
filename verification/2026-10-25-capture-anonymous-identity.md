# Keep unidentified photographed products separate

Product SKU generation hashes normalized name, brand and size. Two distinct
groups labeled ??? with no brand therefore received the same SKU, including
when both had a 500 ml size. A concrete capture produced prices 199 and 799 with
the identical SKU cap_189f808ba0. That falsely asserted a shared product identity
before any attempt to match the existing catalog.

When name and brand contain no usable normalized text, item construction now
uses the existing anonymous-capture SKU formula: capture salt, shelf band and
position within that band. The application supplies the capture ID as salt.
Those items remain stable when the same capture is reprocessed, distinct at
different positions, and distinct across capture IDs. Size alone does not
establish identity. The raw label, model confidence, printed price and other
capture metadata stay intact. Usable names or brands retain their existing
cross-capture SKU behavior. Previously saved capture data is not migrated.

Twelve actual LiteLLM/Instructor HTTP cases cover both JSON modes, three
punctuation-only names, present/absent pack sizes, two different product images
and prices, repeat cache use and two capture salts. Four controls preserve
ordinary, Korean and brand-only identities. Before the fix, twelve tests failed
and four passed in 2.52 seconds.

The focused anonymous/empty identity, ambiguous catalog matching, optional
metadata and printed-price suite passed 168 tests in 4.28 seconds. Full source
Pyright reported zero errors and warnings. There were 24 known LiteLLM
asynchronous logging cleanup warnings. Responses are scripted; no native
inference, model downloads or paid calls ran.
