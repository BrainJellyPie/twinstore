# Keep the structured attempt budget on remote self-hosted servers

The client disabled nested SDK retries only for loopback endpoints. A named
llama.cpp, vLLM or custom server on another machine therefore sent nine HTTP
requests for a three-attempt structured task. Timeouts and HTTP 429/503 failures
multiplied waits as well as requests, despite the harness already owning retries.

Named local provider resolution now sets a runtime-only structured SDK retry
policy of zero. The client applies it only to structured calls. Named cloud
providers and raw model references clear that resolved override; the existing
loopback rule remains. Raw text, which has no Instructor attempt loop, retains
its SDK retries. Successful response cache identity is unchanged because this
policy only controls transport attempts. It is excluded from configuration dumps.

Thirty-six new cases use the actual LiteLLM, Instructor and OpenAI clients with
scripted HTTP: three providers, private IPv4/IPv6 and a hostname, sync/async text
and image calls, and HTTP 503, HTTP 429 and timeouts. The SDK keeps its real retry
decisions; tests bypass only its backoff delay. Before repair every case sent
nine requests instead of three. Four additional real-client controls verify raw
text and transitions to named-cloud/raw references, plus dump exclusion.

Before repair: 36 failed in 4.60 seconds. After repair: 196 focused provider,
retry, usage, template and capacity tests pass in 8.51 seconds. Full-source
Pyright reports zero errors and warnings. Tests emit 24 existing LiteLLM logging
coroutine warnings. No full suite, paid calls, model weights or native inference
were used. The tests establish request counts, not real server response times.
