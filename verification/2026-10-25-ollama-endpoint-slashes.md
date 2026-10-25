# Native Ollama endpoint trailing slashes

The installed LiteLLM Ollama adapter appends `/api/chat` verbatim unless the base
already ends in that exact suffix. A saved `http://127.0.0.1:11434/` produced
`//api/chat`; a full `/api/chat/` URL produced `/api/chat//api/chat`. An address
that passed readiness checks could consequently fail every generation request.
Ollama registers the exact native route in its
[pinned server source](https://github.com/ollama/ollama/blob/d44c2581904a98430e348d89cc2af1529b1808a0/server/routes.go#L2409).

The native chat client's effective endpoint now trims trailing directory slashes
before invoking the adapter. The original configuration and saved provider
settings remain unchanged. Other provider URLs and query/fragment values are
not rewritten; this change does not add native query-string endpoint support.

Sixty HTTP-path cases cover saved and raw configs, five call modes, IPv4, IPv6,
localhost, repeated slashes, a reverse-proxy path prefix, a full chat route and
an already canonical address. Three isolation controls preserve other-provider
and query/fragment inputs. Before repair, 50 cases failed with the fixture's
404 for an incorrect route and 13 controls passed in 26.31 seconds. Successful
structured calls are reused from cache; text uses its existing uncached path.

All 295 focused endpoint, Ollama schema, credential, slot, cache and fallback
tests pass in 5.43 seconds. Full-source Pyright reports zero errors and warnings.
The tests emit 128 existing LiteLLM logging coroutine warnings. HTTP fixtures
exercise real SDK request construction; no native inference, model weights,
paid calls or full suite were used.
