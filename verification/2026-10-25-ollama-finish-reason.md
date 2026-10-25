# Native Ollama output-limit recovery

LiteLLM 1.83.4 hardcoded the native non-streaming response's finish reason to
`stop`, discarding Ollama's `done_reason=length`. Instructor therefore accepted
syntactically complete cutoff replies, or reported incomplete JSON as an ordinary
validation failure. Customer generation's bounded truncation recovery never
received the typed failure and could omit the whole customer batch.

The dependency and lock now require/use LiteLLM 1.84.0, whose native response
adapter preserves this field. The upstream repair is
[3cbb36aa](https://github.com/BerriAI/litellm/commit/3cbb36aa130e3c865b9f04dd7de4fe5c66f295ae).
Only LiteLLM changes in the final lock; existing OpenAI, aiohttp and all other
dependencies remain at their previous versions. Latest stable 1.106.3 was
evaluated but cannot resolve with this project's `python-dateutil>=3.0.0`
because its required boto3/botocore needs dateutil below 3. Earlier 1.83.9 has
the fix but forces unrelated package downgrades. 1.84.0 avoids both conflicts.
An obsolete comment about LiteLLM's exact tokenizer pin was removed; the
existing optional capture dependency bounds are unchanged.

Native Ollama cache identities gain a finish-reason policy marker so previously
accepted cutoff answers are not reused. Other provider cache identities stay
unchanged. Existing bounded application recovery owns any decomposition; the
client introduces no additional attempts.

The new 44 cases use real LiteLLM and Instructor with scripted native HTTP:

- Text/image, sync/async and JSON/JSON-schema modes reject both parseable and
  incomplete length-cutoff JSON, obey the two-attempt budget and write no cache.
- Normal, null and empty finish reasons keep the SDK's successful-stop fallback
  and cache reuse. Native token usage includes failed attempts.
- Customer batches of 4, 5 and 12 recover in two children, preserve every visit's
  time and identity, cache only complete children and reuse them on repeat.
- A legacy cache entry with the old exact hash cannot bypass cutoff validation.

Before repair: 20 failed, 24 passed in 2.38 seconds. After repair: 389 focused
SDK, Ollama schema/endpoint, customer recovery, retry, cache, provider-option,
credential and context-capacity tests pass in 7.49 seconds. Full-source Pyright
reports zero errors and warnings; backend import smoke passes. Tests emit 131
LiteLLM logging coroutine warnings of the existing kind. No paid calls, model
weights, native inference or full suite were used. Actual model quality and
native cutoff frequency remain unmeasured.
