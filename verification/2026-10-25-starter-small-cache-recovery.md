# Let failed small assortment tasks retry without poisoned cache entries

Small catalog tasks checked membership, SKU uniqueness and the global category
budget after the LLM client had already cached their responses. Unknown IDs or
duplicate SKUs could therefore remain in both the original and correction
cache entries. A later attempt replayed those invalid choices without reaching
a provider that could now answer correctly.

BoundedCatalogChoices now runs its existing semantic checks as a response model
validator, after identifier normalization. Instructor can correct a bad choice
before it becomes a cached success. Cached choices written by earlier versions
also undergo these checks and are ignored when invalid. External validation
remains for the selection-client contract; primary task correction and bounded
decomposition remain unchanged.

Six initial HTTP regressions reproduced the failed-repeat behavior. Twelve
final cases cover JSON/JSON Schema, unknown category/SKU, duplicate SKU and
explicit legacy-cache injection. They use real LiteLLM/Instructor and scripted
HTTP replies, then verify renewed provider calls, successful physical filling,
no partial store mutation, only valid small-task cache entries and successful
cache reuse. No native model or paid call was used.

The broader focused suites passed 170 checks initially; eleven direct-fake
call-count expectations needed adjustment because validation now rejects an
invalid small response before the external correction attempt. The changed
tests and new regressions passed 23 checks in 2.41 seconds. Across the focused
small-task, adaptive-batch, category-budget, repair, grammar and API suites,
181 distinct checks passed. Full source Pyright reported zero errors and
warnings. No model download or model error-frequency measurement was performed.
