# Recover large product catalogs without a request for every department

Based on main `d9d5a15c`. Actual runs used Qwen3.5-2B Q4_K_M,
llama.cpp b11878, CPU only, five threads and an 8,192-token context.
The hypermarket has 51 grouped sections and 198 accessible physical racks.
Its previously recorded, real JSON category response selects 44 categories;
that single application-cache entry was explicitly reused to isolate product
selection. Product responses were generated afresh, not mocked.

The original product request was 24,449 tokens and received two HTTP 400
context rejections through the SDK. Recovery then requested one category
at a time. A bounded diagnostic completed the first three such calls and
deliberately stopped before the fourth: five HTTP calls, 23.99 s, one
category-cache hit. It did not finish stocking. The code would continue
over the remaining categories; this is not a measured 44-call baseline.

Recovery now tries up to eight categories together, using a schema and
product-limit map containing only that batch. Failed batches shrink, and
the reduced size persists. The single-category format remains the final
fallback. One to three outstanding categories retain targeted individual
repair. Preserve valid primary selections, successful batches, original
category order, currency-specific identities and capacity limits. Provider
authentication/connection failures still propagate; no partial assortment
is returned or written when a later batch fails.

The first actual batched run completed six successful product requests
after the two context rejections: 347.75 s, 44 selected/placed SKUs, 1,772
placements, no final validation issues. However, its JSON responses often
copied every candidate despite a limit of one. Existing validated subset
repair made the final assortment legal, but output still cost 3,753 tokens.

The product prompt now explains that the per-category limit is a count of
selected products and that candidate lists/schema enums must not be copied
wholesale. For a limit of one, request exactly one code. A comparison of
the same first batch returned one valid code for all eight categories:
123 output tokens versus 597, 36.10 s versus 56.68 s observed.

The complete new-prompt run returned exactly one SKU for every one of the
44 categories before subset repair. Six successful product requests plus
two context rejections, one category-cache hit, 697 output tokens,
182.40 s. It again passed all final placement checks: 44 SKUs, 198 racks,
1,772 placements, unchanged source store, exclusions, limits and catalog
prices. These checks do not prove every department/product is semantically
ideal for the description. Prompt-prefix caching differed between runs,
including a warm first batch, so elapsed times are not controlled speed
benchmarks. Reduced output and correct raw selection counts are observed.

The complete new-prompt diagnostic was initially intended as a native-mode
comparison, but changing a private output-mode attribute did not rebuild
Instructor. Inspection of every captured HTTP request found `json_object`;
the run is classified as JSON evidence. Its separate scratch cache and
`wire-mode-observation.json` record this limitation. No native-grammar
claim is based on it, and no production client configuration changed.
The checked-in probe now records actual wire output modes as well as the
configured mode. A separate direct request using the captured batch schema
did use `json_schema`: eight valid one-SKU selections, one HTTP call,
27.00 s, 123 output tokens. That check covers one product batch, not an
entire native-mode setup.

A fresh full bookstore run checks a different bound and smaller catalog:
JSON mode, maximum two products/category, USD, no application-cache hits.
The model returned exactly two books and two stationery products, rather
than all eight candidates per category as before. Two HTTP calls, 35.05 s,
four selected/placed SKUs and 80 placements; all final checks passed.
Artifact: `product-batches-final/book-json-1793005844787848165`.

Artifacts under `/workspace/scratch/cpu-vlm-probe-2b/`:

- Original bounded diagnostic: `hypermarket-json-1793004912981433307`
- Batching with the old prompt: `hypermarket-json-1793005125236533715`
- First-batch wording comparison: `product-limit-wording-1793005483125174139`
- Complete new prompt, actual JSON wire mode:
  `native-products/hypermarket-json-1793005576098588147`
- Actual native-mode batch: `product-batch-native-1793005804059055148`

Integration also includes `7675a25f` and `dad86102`: accessible product-name,
category and price fields in shelf-photo correction, and a distinct message
when there has never been a saved capture queue.

Verification: 209 affected backend tests passed in 11.16 s, including
adaptive product batches, invalid/cross-category/duplicate selections,
partial primary recovery, old cache behavior, provider failures and API
integration. The initial five new batch tests failed against the previous
implementation; all seven final tests passed with this change. Strict
backend Pyright reported zero errors/warnings and the backend import smoke
passed. Four affected frontend files passed 102 tests in 4.94 s.
Changed-source ESLint and TypeScript checking passed; production build
passed in 19.96 s with chunk-size/plugin-time warnings. Probe compilation
and `git diff --check` passed. The full repository suite was not run.
