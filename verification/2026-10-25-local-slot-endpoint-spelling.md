# Preserve local slots across equivalent endpoint spellings

Named llama.cpp resolution looked up known server slots using raw URL equality.
A ready server at /v1 was therefore treated as having unknown capacity when its
provider setting ended in /v1/. Host-name casing had the same effect. With the
default unlimited client, every shopper/generation request could enter the local
server queue at once, where request timeouts run while waiting.

Slot lookup now uses the existing concrete-endpoint identity check. It ignores
trailing path slashes and canonical host casing while retaining scheme, host,
port, path, query and credentials. Different loopback aliases can serve different
models and remain separate. Unavailable states and unknown slot counts preserve
the existing configured request limit.

The scripted HTTP fixture drives real LiteLLM/Instructor clients and records
simultaneous requests from a six-call batch. It covers one/two slots, exact and
equivalent URLs, JSON/JSON-schema text and image calls, and raw text completion.
Before the fix, twenty equivalent-spelling cases failed, sending six requests at
once; twenty-one exact-address, separate-endpoint and state controls passed.
After the fix, peak active requests match the reported one/two server slots.
The fixture does not run a native model or reproduce an actual inference timeout.

All 332 focused capacity, endpoint identity, readiness and credential checks pass
in 5.21 seconds. Full-source Pyright reports zero errors and warnings. The run
emits 59 existing LiteLLM logging coroutine warnings. No full-suite run, paid
inference or model weights were used.
