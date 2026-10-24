# Require primary model actions before executing a visit

The catalog-bound intent response defaulted a missing actions field to an empty
list. An empty response or narration-only response could therefore be cached
and executed as a successful visit without the model providing a plan. The
same gap affected the focused action request after context-limit recovery.

Require actions in primary model response schemas. Keep internal IntentResponse
construction defaults, explicit empty lists and the optional ImpulseResponse
contract, including its null/omitted reaction list. A class-level flag carries
that distinction into the shared catalog-response factory. Clarify the primary
prompt without increasing retry budgets or changing execution semantics.

All 33 new cases failed before the fix in 4.12 seconds. Scripted HTTP covers
both JSON modes, planned/nearest routes, full/focused requests, empty/narration-only
responses and invalid legacy caches. Missing plans fail before an impulse
request; later complete plans buy the exact selected offer, retain quantity
and revenue, pay once and exit. Cached repetition preserves the same visit,
while an omitted additional impulse list remains valid.

After the fix, 279 focused intent, context recovery, optional impulse, catalog,
quantity and engine-field checks passed in 12.50 seconds. Pyright reported zero
errors and warnings. The nine pytest warnings are existing LiteLLM async logging
cleanup warnings. No native model inference or model download was used.
