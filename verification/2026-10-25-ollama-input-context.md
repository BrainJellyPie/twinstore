# Preserve native Ollama inputs and recover explicit overflow

Ollama defaults `truncate` to true. Its prompt builder can discard earlier
messages, and its text runner can discard input tokens, so a valid JSON answer
does not prove that all customer requirements or product choices reached the
model. Protocol evidence is pinned to Ollama v0.40.11:
[request fields](https://github.com/ollama/ollama/blob/v0.40.11/api/types.go),
[chat handler](https://github.com/ollama/ollama/blob/v0.40.11/server/routes.go),
[prompt construction](https://github.com/ollama/ollama/blob/v0.40.11/server/prompt.go)
and [text runner](https://github.com/ollama/ollama/blob/v0.40.11/llm/llama_server.go).

Native `ollama_chat/` calls now send top-level `truncate=false`, including raw
text and structured sync/async text/image calls. This is an API body control,
not an entry in `options`. Cache identities exclude answers obtained under the
previous input policy. Other protocols do not receive this native parameter.

The real LiteLLM adapter additionally maps native HTTP 400 to APIConnectionError
with a synthetic status 500. The context classifier now recognizes this exact
adapter shape only when its cause chain retains an original HTTP 400 response.
Original non-400 statuses remain authoritative, including failures in a child
request during parent-overflow recovery. Ollama's precise prompt-too-long
message joins the existing concrete llama.cpp messages. Generic context wording,
connection failures without HTTP evidence, auth, rate limits and server errors
do not authorize decomposition.

Thirty-two new boundary cases exercise real LiteLLM/Instructor with scripted
native HTTP: five call modes, both JSON modes, HTTP 400/401/403/429/500,
unsupported-parameter controls, legacy cache isolation and other protocols.
Starter selections with 1, 9 and 17 racks recover through smaller tasks while
preserving every rack and the full requirements. If even one rack cannot fit,
or its child request fails with 403/429/500, the task stops after four requests
without partial store changes. A valid but wrong-category fixture represents
the risk of successful output after silent input loss; it is not a measurement
of any native model's behavior.

Initial reproduction: 15 failed, 12 passed in 2.63 seconds. Additional child
failure boundaries exposed the nested synthetic error wrapper and are covered
by the final classifier. Final focused run: 244 tests pass in 4.95 seconds;
full-source Pyright reports zero errors and warnings. Tests emitted 64 existing
LiteLLM logging coroutine warnings. No full suite, paid calls, weights or native
inference were used. Older Ollama versions may not enforce this optional API
field; native server/model behavior outside the pinned protocol was not tested.
