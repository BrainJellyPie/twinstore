# Validate receipt numbers before caching and conversion

Receipt OCR accepted `NaN` and infinities as floats in its model-response schema.
The client cached these responses before receipt construction rejected the quantity
or price conversion raised an exception. Non-finite optional prices could also
serialize to null in that cache, making a later attempt see different data.

Require finite quantities, unit prices, line totals and receipt totals in the model
response itself. Ask for null when an amount cannot be read. Allow two model
attempts in total so invalid structured output can receive one correction before
the photo is reported as failed. The changed prompt also gives these requests a
new cache key instead of reusing entries produced under the old instructions.
Finite negative and zero values remain available for the existing manual review;
explicit unknown amounts remain null. No guessed price is substituted.

The regression uses an HTTP mock transport through the real OpenAI client,
LiteLLM, Instructor validation, disk cache and receipt conversion. Across four
numeric fields and three invalid values (`NaN`, `Infinity`, `-Infinity`), it checks
both a valid correction and repeated invalid replies. Successful correction takes
exactly two HTTP requests, then the next read uses only the corrected cache entry.
Repeated invalid replies stop after two requests and create no response entry.
Finite USD/KRW amounts, returns, zeros and unknown prices are separate controls.

Before: 24 failing cases and 2 passing controls. After: 124 focused receipt,
currency, review, timestamp and API-isolation checks passed in 5.22 seconds.
Strict Pyright reported zero errors in the changed module; `git diff --check`
passed. All HTTP requests were intercepted offline; no live model calls were made.
