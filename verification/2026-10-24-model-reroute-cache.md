# Preserve provider identity when concurrent model requests reroute

A structured request computed its cache path before waiting for a concurrency slot. Another
request could switch the shared client to a fallback model or endpoint while it waited. The queued
request then sent to the new provider but cached its answer under the old provider. A later run
using the original provider could reuse that answer without calling its own model.

Each configuration now has an identity token. Queued requests re-enter the request loop when that
identity changes, selecting the correct cache path and provider semaphore. If configuration changes
during an in-flight call or its internal retries, its answer is returned without writing to a cache
path whose provider is uncertain. Unchanged requests retain caching, and queued fallback responses
are cached under the fallback. Raw text requests also refresh provider arguments after waiting.

Parameter-rejection learning uses the model in the actual sent arguments. An old provider's delayed
unsupported-temperature error can no longer disable temperature for a different fallback model.

Focused offline evidence:

- Four queued/synchronous cache races failed before repair (**2.60s**), covering different model
  IDs and the same model ID served at different endpoints.
- An additional real async retry using fake provider adapters failed before repair (**2.34s**):
  an original-provider error incorrectly removed temperature from the fallback's request.
- Final concurrency, cache, malformed-entry, thinking-parameter and key-fallback tests:
  **66 passed in 3.16s**. Changed module strict Pyright: **0 errors**.
- One intermediate test reused the parameter-learning registry between parameterized cases;
  unique fake model IDs corrected that fixture contamination.

All provider responses are scripted; no live model calls, full suite, frontend or release changes.
Existing cache files are not deleted or globally invalidated. Provider-specific provenance cannot
be recovered from older cache entries, which stored only the response.
