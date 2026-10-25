# Reject reversed model search ranges before matching

A model could write `min_spent: 20, max_spent: 10` for a request to find shoppers
spending between 10 and 20. The filter was accepted and cached, producing no
matches and suggested near misses instead of retrying the malformed range.
The same issue affected minimum and maximum visit duration.

Validate these pairs in the model-only filter used by `find_shoppers`, before
matching or caching. A minimum above a supplied maximum triggers the existing
two-attempt correction path; persistent failure remains a model error. The
prompt explains ordering, inclusive equal bounds, null for an unspecified limit
and zero as a real bound. No limits are swapped or dropped automatically.

Equal, zero and one-sided ranges remain valid. The generic `_Filter` and direct
`apply_filter` behavior remain compatible with explicitly supplied legacy
filters, including their empty results and near-miss explanations. The cache
reader also revalidates a seeded invalid entry and obtains a valid replacement.
The prompt change gives old searches a new cache identity.

Twenty-four real LiteLLM/Instructor HTTP cases cover JSON and JSON-schema modes,
spend and duration, USD and KRW, correction, repeated failure, a later successful
retry and invalid-cache recovery. Ten controls cover equal, zero and one-sided
model ranges, and one preserves the direct legacy-filter behavior.

Before the fix, 24 cases failed and 11 passed in 2.67 seconds. The focused range,
clock, numeric-boundary and shopper-search API suite passed 272 tests in 6.20
seconds. Full source Pyright reported zero errors and warnings. The eight test
warnings were existing LiteLLM async logging cleanup warnings. No native model
inference, model downloads or paid requests ran; HTTP replies are scripted.
