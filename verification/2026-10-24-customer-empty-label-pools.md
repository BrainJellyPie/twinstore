# Keep empty profile pools coherent across generation stages

The area model could return empty customer-type or purpose lists. Runtime traffic
recovery already uses the generic `shopper` identity when no types are known, but
the traffic and persona prompts still required choosing from the original empty
lists. This contradiction could produce blank labels or failed customer batches.

The local profile schema now requests at least one identity and one purpose.
Runtime validation still accepts empty lists from non-enforcing providers. In
that case, traffic and persona prompts both use `shopper`, and persona writing
uses the generic purpose `shopping`. Existing nonempty labels are copied unchanged;
empty keywords remain valid, null/non-list pools remain invalid, and the original
profile object is not modified. No extra requests, fabricated demographic details
or new visitor-count fallback are introduced.

Nine HTTP regressions failed before the patch; one structural control passed.
Coverage includes JSON, schema-enforcing scripted responses and schema-ignoring
responses; either/both missing pools; downstream label consistency, two weekdays,
original visitor counts, unique IDs without twins and cache reuse. Related label
length, traffic, source-evidence, batch-count, missing-day and write-choice checks
also pass: 159 cases in 8.75 seconds. Strict Pyright: zero errors. Responses were
scripted and no live inference was used.
