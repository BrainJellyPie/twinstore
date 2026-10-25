# Keep specifically requested products in bounded model catalogs

The shared catalog selector treated every entry sharing any query word as an
equal match. With 200 ordinary teas before Saffron tea, a request naming Saffron
tea omitted that product from every bounded prompt: all generic tea matches
occupied the available entries first. This affected layout edits, scenario
promotions, experiments, shelf tests, conjoint drafts, survey drafts and test
suggestions.

Matching entries now rank by the number of shared product-text words, followed
by shared product/shelf words. A plural and its generated singular count as one
clue. Equal scores preserve input order; unmatched entries still rotate among
shelves, and existing prompt limits remain unchanged. This is lexical ranking,
not a claim to understand every paraphrase or language-specific inflection.

Six bounded listing paths are checked with singular and plural English, Korean
and French queries. Six limit/tie cases preserve stable order. Sixteen HTTP
cases use real LiteLLM and Instructor with scripted responses in both output
modes. They require the named product in the supplied catalog, then apply the
returned scenario, layout, experiment or shelf-test change: only the requested
SKU becomes 80 cents, while the other 200 remain 100 cents. Repeated calls use
cache and source stores remain unchanged.

Before the repair, 35 cases failed and 12 passed in 9.13 seconds. The final
focused suites passed 158 checks in 4.86 seconds, with 63 known LiteLLM logging
cleanup warnings. Full source Pyright reported zero errors and warnings. No
native inference, model downloads or paid calls were used. The tests verify
prompt contents and change application; they do not measure how often a real
model would omit or substitute a product when its catalog is incomplete.
