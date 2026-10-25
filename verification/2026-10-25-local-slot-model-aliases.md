# Follow local endpoint capacity across model aliases

Equivalent URL spelling alone was not enough to preserve request limits. Only
the special llama.cpp model id local received known slots during named-provider
resolution. Another llama.cpp id, a custom/vLLM reference pointing at the same
server, or a raw OpenAI-compatible id using its actual alternate port could send
unlimited requests. Existing explicit limits were also handled inconsistently:
the special named alias could raise a smaller limit, while a raw reference could
bypass the server capacity with a larger one.

Named references now look up slots by their resolved endpoint. Raw references
already using the active endpoint receive its capacity too; the existing redirect
from the usual managed address to its actual port remains. Where a client limit
is present, the smaller of it and the known server slots applies. Independent
endpoints retain their own configuration and model identity.

Thirty-six scripted-HTTP cases cover the special/named llama.cpp ids, custom and
vLLM aliases, raw actual-port and usual-address references, text/image output,
and limits of None/one/four against a two-slot server. Each submits six concurrent
requests through real LiteLLM/Instructor clients. Before the fix, twenty cases
failed and sixteen controls passed. Peak requests now respect the smaller limit.
These are per-client limits, not a new global scheduler across separate jobs.

All 393 focused capacity, endpoint isolation, credential, managed-cache and
provider-fallback checks pass in 7.53 seconds. Full-source Pyright reports zero
errors and warnings. The run emits 59 existing LiteLLM logging coroutine warnings.
No full suite, paid request or native model execution was used.
