# Bound customer output to the current request

Every customer-generation request previously advertised `maxItems=12`, even when
the probe, a local batch, a final partial batch or a truncation-recovery child
asked for just one to five customers. A grammar-capable model could generate
unneeded records and run out of output room before returning a usable batch.

Each request now gets its own `PersonaBatch` schema with a transmitted maximum of
the requested count (up to the existing twelve-record ceiling). The prompt also
asks for one person per supplied row in order, without extra or repeated people.
The base model remains unchanged. Runtime validation retains the existing
one-to-twelve allowance for servers that ignore the JSON schema, so short valid
responses can still fill populations with twins and surplus records are clipped
as before. Concurrent requests do not change one another's schema or global state.

Before: ten new failures and one twelve-record control passed. After: 180 focused
customer grammar, truncation recovery, traffic, prompt-boundary, missing-day,
sample-probe and budget checks passed in 4.14 seconds. Cases cover requests of
1/2/5/10/12 customers, final batches from totals of 6/11/13, repeated cache use,
short/surplus replies and concurrent different-sized requests. HTTP checks
inspect the serialized OpenAI schema through LiteLLM and Instructor, rather than
only inspecting prompt text. Three existing test fixtures now recognize
request-local schema subclasses.

Strict Pyright reported zero errors and diff whitespace checks passed. One
existing LiteLLM logging-worker coroutine cleanup warning appeared in the focused
run. No model weights, live inference or paid calls were used. This verifies the
output constraint and compatibility paths, not physical-model generation speed.
