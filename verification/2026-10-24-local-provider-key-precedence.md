# Prefer the configured local key for named self-hosted providers

The llama.cpp and vLLM presets did not declare an environment key. Their resolved
configurations therefore omitted PARASTORE_LOCAL_API_KEY. The client used that
key as a fallback only when OPENAI_API_KEY was absent. With both variables set,
the OpenAI SDK sent the cloud credential to a local server, which could reject
the request despite its valid local credential being configured.

Both presets now resolve PARASTORE_LOCAL_API_KEY using the existing provider
credential resolver. Keys entered in Provider Settings still win, whitespace is
handled by that resolver, keys remain excluded from serialized configurations,
and keyless local servers remain supported. This change applies to named
llamacpp/vllm references; it does not reinterpret arbitrary raw endpoint configs.

Forty HTTP cases cross both providers, synchronous/asynchronous text and image
calls plus raw text completion, environment versus saved keys, and an OpenAI
key present or absent. The real SDK request Authorization header is checked by
mocked HTTP; an incorrect credential receives 401. Three additional controls
keep the OpenAI, Anthropic and Gemini keys independent of the local key.

Before: 10 actual authentication failures and 33 passing controls. After:
92 focused credential, provider readiness, fallback and local connection checks
passed in 4.01 seconds. Strict Pyright reported zero errors and
`git diff --check` passed. The test process emitted 24 LiteLLM event-loop/logging
cleanup warnings while opening and closing test loops; no assertion failed.
Only synthetic offline credentials and mocked HTTP were used.
