# Preserve generation constraints on native Ollama requests

The Ollama preset inherited ordinary JSON mode. Instructor included a schema in
the prompt, but LiteLLM sent only `format: "json"` to `/api/chat`. Rack identity,
catalog SKU, list-length and numeric bounds were therefore absent from the
server's generation constraints, despite the dynamic grammars already built by
TwinStore's automatic selection pipeline.

Named local Ollama models now use JSON-schema mode. LiteLLM translates the schema
to Ollama's native `format` object for text and vision calls. Validation and
semantic recovery remain active; a schema alone cannot enforce every cross-row
relationship. Cloud-tagged models (`:cloud` or `-cloud`) and the `ollama.com` host
retain JSON mode because [Ollama's documentation](https://docs.ollama.com/capabilities/structured-outputs)
states that Cloud does not support structured outputs. Raw model configurations
retain their explicitly selected mode.

Twenty-four new cases exercise the real LiteLLM/Instructor HTTP serialization,
including four text/image sync/async call paths, served aliases, cache reuse,
one/two/seven/thirteen racks, nonsequential IDs, Unicode, escaping, case-distinct
IDs and USD/KRW/JPY. Dynamic category and product schemas accept the selected
rows and reject invented rack IDs or SKUs. Four cloud controls complete a request
against an HTTP fixture that refuses schema objects.

The initial fixture counted LiteLLM metadata lookups as generation requests.
After separating `/api/show` and retaining immutable request snapshots, rerunning
with the previous preset produced 20 failures specifically from missing schema
objects and four passing cloud controls in 0.53 seconds. These tests establish
the transmitted constraints, not a measured rate of native model mistakes.

All 148 focused Ollama, starter grammar/cache, customer grammar, local readiness,
template-policy and fallback tests pass in 4.57 seconds. Full-source Pyright
reports zero errors and warnings. The test run emits 25 existing LiteLLM logging
coroutine warnings. No full suite, paid request, downloaded weights or native
model inference was used.
