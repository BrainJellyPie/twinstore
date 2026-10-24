# Reach the local model after multiple rejected cloud keys

Assistive requests can try four cloud providers with suggested models before
using the local model. A user-selected OpenRouter model can precede those four.
The generic client stopped after three provider switches, so the last configured
cloud rejection escaped before the application could select a ready local model
or explain that no usable model was available.

Give clients an optional bounded reroute budget, preserving the existing generic
default. The assistive factory sets its budget from the application's fallback
provider list, allowing one rejected key per cloud provider followed by local
inference. The engine does not import application provider policy. Authentication
failure remains the only reason to switch; ordinary simulation clients still
have no reroute callback.

Sixteen offline regressions cross an ordinary first provider or a user-selected
OpenRouter model, synchronous/async/image/raw-text calls, and a ready or unavailable
local server. They exercise real configuration resolution, rejected-key tracking
and fallback selection while mocking inference. A ready local model must answer
after each configured cloud model was tried once; an unavailable local model must
produce the actionable application error without being called. A cyclic callback
control confirms the generic client's original finite budget remains effective.

Before: 16 failures and the cycle control passing. After: 78 focused fallback,
concurrency, cache-reroute, provider readiness and retry-boundary checks passed in
3.65 seconds. Strict Pyright reported zero errors in both changed modules;
`git diff --check` passed. No actual credentials or live provider requests were used.
