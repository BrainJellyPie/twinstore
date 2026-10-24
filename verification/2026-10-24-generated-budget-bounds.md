# Reject unusable model-generated customer budgets

The generated-customer schema accepted arbitrary nonnegative integers for budget
fields. An oversized model answer could be cached and become a saved customer;
formatting a 401-digit USD budget then raised `OverflowError`. Smaller values
above 2^53 - 1 also could not be represented exactly in the browser.

Give both generated budget fields the existing browser-safe money bound used
elsewhere in the application. The provider schema and local validation now reject
oversized amounts while Instructor can still request a corrected answer. The
prompt asks for realistic single-visit amounts and zero when no budget can be
specified. The schema and prompt changes also separate new requests from old
cached answers. Existing saved/imported customers are not silently rewritten.

Offline HTTP regressions exercise OpenAI transport, LiteLLM, Instructor, the
complete customer-generation pipeline and response caching. Cases cross both
budget fields, the first unsafe integer, a 401-digit integer and its string form,
with a corrected second response or repeated invalid responses. Corrected
customers remain usable and the next generation reuses their valid cache;
repeated bad amounts exhaust three attempts and fail the generation without
caching the customer. Numeric-string cases were already rejected by the strict
transport validator and remain controls. Boundaries retain zero, one and the
largest safe integer.

Before: 10 failures and 10 passing controls. After: 111 focused customer-generation,
prompt, concurrency, missing-day and simulation-budget checks passed in 3.18
seconds. Strict Pyright reported zero errors; `git diff --check` passed. No live
inference, model download or paid provider call was used.
