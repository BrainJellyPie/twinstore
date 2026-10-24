# Avoid multiplying local structured-request retries

OpenAI-compatible local requests inherited the SDK's default two retries inside
each Instructor attempt. With three structured attempts, a persistent HTTP 503
caused nine HTTP requests. Timeouts could similarly spend multiple transport
attempts inside a single outer attempt, delaying failure or fallback.

Structured requests to `localhost` or an IP address classified as loopback now
pass LiteLLM's `num_retries=0`; Instructor retains ownership of the configured
attempt count and its existing retry timing. Text/image and sync/async calls use
the same policy. Raw text has no Instructor budget and retains SDK retries, as
do non-loopback endpoints (including LAN servers). Provider-option negotiation,
context adaptation and configured model fallback remain separately bounded as
before. This does not impose a new wall-clock timeout or preserve the removed
SDK layer's backoff/Retry-After scheduling for local structured calls.

An initial probe recorded nine HTTP requests for three attempts. The new matrix
then had 36 failing cases and 13 passing controls. After repair, 177 focused
retry-budget, output-budget, customer/starter-context and provider-option checks
passed in 5.33 seconds. Eleven added timeout/address checks passed in 2.28 seconds,
for 188 unique checks. Coverage includes persistent 503/429 and timeouts, one or
three attempts, transient failure and validation recovery, text/image, sync/async,
IPv4/IPv6/localhost spellings, remote/lookalike hosts, raw text and actual HTTP
body contents. Unlike earlier HTTP fixtures, these tests keep the real SDK retry
defaults instead of overriding them with test-only `num_retries=0`.

Strict Pyright reported zero errors. Three existing LiteLLM asynchronous logging
cleanup warnings occurred in the focused run. HTTP requests use mock transports
through OpenAI, LiteLLM and Instructor; no live inference, model downloads or paid
calls were used.
