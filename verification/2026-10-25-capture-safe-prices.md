# Keep unrepresentable shelf prices out of the planogram

Finite model guesses such as 1e306 and a 21-digit printed tag passed shelf
price conversion and became exact prices. Applying a capture could overwrite
an existing product's price with an integer beyond the browser-safe range.
The conversion now treats these amounts as unreadable using the existing
MAX_PRICE limit. Thousand-unit interpretations also respect that limit.
Normal currency, cent and catalog-estimation semantics remain intact.

Twenty-four regressions exercise real LiteLLM/Instructor over scripted HTTP
in JSON and JSON Schema modes: USD/KRW, numeric guesses, long tags and the
first unsafe integer, with existing and new products. They reproduce wrong
placed prices before the fix, then verify actual rack replacement, preserved
neighbor prices, estimated-price flags, unchanged source stores and cache
reuse. Explicit boundary controls retain the largest supported cent/yen/won
amounts and reject the next integer. Existing four-currency boundary tests
now require every returned amount to stay within MAX_PRICE.

The initial focused run passed 933 checks in 3.75 seconds. Two additional
thousand-unit test inputs were corrected to actually exceed the upper bound;
both then passed in 1.83 seconds, for 935 distinct passing checks. The focused
scope includes price text/currency parsing, catalog matching and ambiguous
SKU controls. Full-source Pyright: zero errors and warnings. Backend import
smoke: OK. No native model, model download, paid call or model error-frequency
measurement was used. Existing LiteLLM logging cleanup warnings remain.
