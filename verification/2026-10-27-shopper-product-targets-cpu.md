# Validate generated product targets before shopper matching

An actual CPU JSON response for shoppers who bought the unavailable product
Moonberry Soda instead puts that name in `skipped_products`. The application
cannot resolve it, leaves the condition out, and returns six customers using
an unrelated shelf condition. The baseline takes 7.65 seconds and one HTTP
request. This includes two distinct failures: the model reverses the purchase
meaning, and the application accepts a product predicate with no usable target.

At the model-response boundary, each nonempty `bought_products` or
`skipped_products` list must now contain at least one resolvable product.
Otherwise validation requests correction before caching or matching. The
resolver and name-to-SKU groups equal those used by the matcher. Existing
case/quote handling, same-SKU aliases, duplicate visible names, empty lists
and partly known lists with warnings remain usable. Direct legacy
`apply_filter` behavior and the production prompt/schema remain unchanged.

The initial new test file has **28 failures and 10 passes in 3.60 seconds**.
After the fix, three related files pass **111 tests in 5.07 seconds**. Four
additional alias/duplicate-name cases join the final nine-file run:
**513 tests pass in 12.27 seconds**, with 111 dependency/resource warnings.
Coverage includes both HTTP output modes, correction and bounded failure,
invalid legacy cache entries, later successful retries, ambiguous and empty
catalogs, unchanged input records and existing shelf/time/spending conditions.
Strict Pyright has zero errors or warnings; application import and diff
checks pass. UI code is unchanged and inherits integration 430's checks.

## Actual CPU results and limits

Use Qwen3.5-2B Q4_K_M through llama.cpp b11878, five CPU threads, no GPU,
context 8192, reasoning off and temperature 0. These are text requests on a
VLM over seven complete synthetic personas and synthetic visits. The five
fresh runs have six real HTTP requests, zero application cache hits and
**zero complete semantic passes**:

| Version / request / mode | Seconds | Requests | Observation |
| --- | ---: | ---: | --- |
| Parent / unavailable product / JSON | 7.65 | 1 | unknown skipped-product condition dropped; six wrong matches |
| Parent / unavailable product / native schema | 26.02 | 2 | unrelated demographic, persona and no-purchase filters; zero matches for wrong reasons |
| Final / unavailable product / JSON | 19.09 | 1 | substitutes exclusions of real listed products; one wrong match |
| Final / known product / JSON | 9.05 | 1 | adds unrequested demographic, spend and duration filters; zero matches |
| Final / excluded product / JSON | 12.06 | 1 | adds purchase, demographic and persona filters; zero matches |

The parent and final unavailable-product JSON request bodies are exactly
equal, but their model replies differ despite temperature zero. The final
fresh reply contains only listed products and does not exercise the new
guard. It is not evidence that the guard repaired the request's meaning.

To test the observed failure independently of that reply variation, one
additional diagnostic replays **only the recorded first baseline reply**,
asserting that its request is unchanged, then sends the correction request
to the real CPU model. The live correction moves Moonberry Soda into
`bought_products`, fixing the purchase direction but still referring to an
unavailable product. Validation rejects it after the existing two-attempt
limit, leaves no JSON cache entry and returns no misleading customer list.
The probe takes 9.82 seconds with **one replayed reply and one live HTTP
request**; its usage counters include the replay and are not fresh-inference
totals. This is successful bounded rejection, not a successful shopper search.

Valid-looking but unwanted criteria, substitutions of listed products and
missing requested conditions remain model limitations. This change prevents
the application from silently dropping an entirely unresolvable product
predicate; it does not make natural-language filtering generally reliable.

Artifacts are under `/workspace/scratch/shopper-product-baseline/`,
`shopper-products-final/` and `shopper-products-reask/`. Exact paths, results
and timings are in `shopper-products-final-summary.json`; initial-request
comparison is in `shopper-products-reproduction.json`. The assisted diagnostic
ends in `missing-json-1793060070804597969` and includes `replay.json` recording
its scope. The driver is `probe_shopper_product_reask.py`; test-file lists,
check timings and logs use the `shopper-products-` prefix. Fresh cases use
`missing`, `known` and `excluded` in `verification/local-filter-probe.py`.
