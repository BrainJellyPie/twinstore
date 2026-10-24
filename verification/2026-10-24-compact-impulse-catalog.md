# Compact downstream impulse prompts

A valid ten-product pattern using adjacency exposure produced a 13,071-token
urban-template impulse prompt (system plus user text), even after intent-stage
context recovery. This could fail the visit at the next model call. Compact and
campus templates measured 9,482 and 11,925 tokens respectively. Default visibility
exposure limits the set to 40 products; it is smaller, but still repeated rack
metadata and long SKU identifiers for every offer.

The impulse prompt now lists each referenced rack's label, type, decoration and
previously shown access tiles once. Product rows retain exposure order and refer
to the rack table, with their original name, price, promotion, level and visibility.
The engine reuses collision-safe intent catalog references for exactly the shown
offers. A request-local action grammar lists those references, and the existing
catalog validator restores canonical SKUs before caching. The schema includes the
hidden SKU binding digest; results are converted back to stable response classes.
Existing unknown/unexposed purchase guards, budgets, product caps and checkout
rules still apply. No exposed products are dropped and no extra model call is added.

Offline Qwen tokenizer measurements for the same ten-product routes:

| Template | Adjacency before | Adjacency after | Visibility before | Visibility after |
| --- | ---: | ---: | ---: | ---: |
| compact_cvs | 9,482 | 3,837 | 4,138 | 2,515 |
| urban_cvs | 13,071 | 5,273 | 4,198 | 2,654 |
| campus_cvs | 11,925 | 4,767 | 4,207 | 2,684 |

Adjacency retained 111, 154 and 140 exposed products respectively; visibility
retained 40 in each case. These counts include system and user text but exclude
chat templates, response-schema overhead and output. Arbitrarily large inputs can
still exceed server context. No live-model behavioral-equivalence claim is made.

Sixteen HTTP contract regressions failed before implementation. Updating an older
scripted client's exact-class dispatch to recognize request-local schemas exposed
two pre-existing checkout regressions: a browsing-only intent's payment was pruned,
then replaced with a default after impulse purchases, losing its original dwell
and selected counter. The engine now reuses that original payment only when a
surviving purchase needs checkout. Existing sanitization and reachability checks
still run during execution, and no-purchase visits still omit payment. Recovery
trace assertions also exposed a reused variable that overwrote the stage-one
pattern with catalog candidates; separate bindings preserve both traces.

An action-text fixture recognizes the impulse subclass so its prompt bound remains
checked. Focused verification passed 357 unique tests: 321 in the initial broad run,
then all 128 affected cases after the fixture, checkout and trace repairs, including
the previously failing 36 controls. Strict Pyright reported zero errors. Seven
existing LiteLLM logging-cleanup warnings occurred in the broad run; the final run
had none.

Coverage includes both JSON modes, route orderings and exposure models; reference-like
real SKUs; canonical purchases, quantities, revenue, traces and cache reuse; two
identical visible catalogs with distinct SKUs, concurrently and sequentially; prices,
promotions, repeated racks, offer variants and exposure ordering; unseen products,
budgets, product caps and checkout. All transports and model responses were scripted;
no live or paid inference was used.
