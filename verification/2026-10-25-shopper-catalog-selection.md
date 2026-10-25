# Supply named products from the whole catalog to shopper search

Shopper search supplied only the first 200 distinct product names, regardless
of the manager's question. The shared relevance ranking did not apply to this
path. A query about Saffron tea at position 201 therefore supplied a catalog
without that product even though the run contained its purchases.

The search listing now uses the manager's text to prioritize products through
the existing bounded selector. It retains the 200-name limit, deduplicates
product names, and shares unspecified catalog space across shelves. Currency
and shelf descriptions remain available.

Eight scripted HTTP cases exercise real LiteLLM and Instructor in both output
modes, with singular/plural questions and bought/did-not-buy conditions. The
request must contain the late catalog product and exactly 200 distinct names;
the resulting search must select the target buyer, or the other buyer and
empty-basket shopper, respectively. Source records remain unchanged and repeat
requests use cache. Additional cases check shelf diversity and empty catalogs.

Before the repair, nine cases failed and one passed in 5.29 seconds. Focused
catalog, choice, range, clock and API suites then passed 205 checks in 7.61
seconds, with 52 known LiteLLM logging-cleanup warnings. Full source Pyright
reported zero errors and warnings. No native model, model download or paid call
was used. This verifies supplied context and deterministic matching, not a real
model's rate of inventing or omitting conditions when context is incomplete.
