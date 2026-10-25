# Preserve the selected shelf for repeated-product tests

Shelf-test drafts had no shelf response field and always selected a SKU's
first rack. Their model listing also deduplicated product names across racks.
A request to test Cola on Drinks 10 therefore selected Drinks 1, even when
the provider explicitly returned shelf="Drinks 10".

The response now accepts an optional shelf name/ID and the prompt asks for it
when the question specifies a location. Catalog entries retain each shelf
and price, with IDs included in bounded query relevance. A supplied shelf
must uniquely identify a location that sells the selected SKU; validation
runs within Instructor before caching. No supplied location keeps the
existing first-placement default. Product-name ambiguity remains an error.

The initial HTTP regressions reproduced twelve wrong selections or accepted
invalid locations. Final checks cover both JSON modes, names/IDs/case/spaces,
reversed rack order, missing shelves, shelves without the product, ambiguous
names, corrected retries, cache reuse, long unique/ambiguous prefixes and
null/blank defaults. A 151-rack case confirms an explicit ID beyond the
150-entry cap is prioritized. The public design API also returns the chosen
rack. Source stores remain unchanged.

Focused location, recovery, identity/price bounds, optional annotations,
catalog relevance and API suites passed 167 checks in 4.64 seconds. After
including IDs in relevance, the affected suites and added large-layout case
passed 71 checks in 2.95 seconds: 168 distinct passing checks overall.
Full-source Pyright after the final edit: zero errors and warnings. Tests
used real LiteLLM/Instructor with scripted HTTP, no native model or paid
calls; native selection accuracy was not measured. Existing LiteLLM logging
cleanup warnings remain.
