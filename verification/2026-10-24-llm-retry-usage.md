# Account for failed structured-output attempts

The LLM client recorded usage only after a structured request succeeded. A
response corrected on the second attempt counted as one request, and an exhausted
or truncated batch counted as zero requests/tokens even when the model reported
usage. Splitting a failed customer batch then understated the work done before
its successful children. This also affected probe accounting and token-based
estimates when a paid provider was used.

Per-call Instructor hooks now count completion attempts. Successful calls add
their extra attempts while retaining Instructor's already-aggregated token totals.
Failed calls record the wrapper's total reported usage and actual attempt count
before optional-parameter adaptation, output-budget adjustment or provider
fallback. Cache hits remain requests with zero additional tokens. Counters are
local to each request and updates use the existing lock. No retry or inference
behavior changes in this patch. Raw-text accounting is unchanged; these counters
describe Instructor/provider completion attempts, not hidden SDK HTTP retries.

Before repair, twenty cases failed and four controls passed. Afterward, 157
focused usage, cache-I/O, cache-key, provider-fallback, output-budget and customer
truncation checks passed in 4.36 seconds. A concurrent-call test and strengthened
customer recovery test passed in 2.35 seconds, for 158 unique checks. They cover
text/image, sync/async, immediate success, corrected output, exhausted validation,
truncation, rejected requests, fallback, cache reuse, reset and concurrent mixed
success/failure. The recovered-customer test records eight HTTP completions and
two cache hits as ten requests and includes all six truncated responses' tokens.

Strict Pyright reported zero errors. Five existing LiteLLM asynchronous logging
cleanup warnings occurred in the broad focused run, with another cleanup warning
after the additional checks. Tests use scripted responses and mock HTTP through
the actual OpenAI/LiteLLM/Instructor stack; no live inference or paid calls were
used. Token totals reflect provider-reported usage and are not billing statements.
