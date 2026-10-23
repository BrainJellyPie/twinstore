# Keep model-option compatibility specific to its server

Rejected optional parameters and thinking-mode hints were keyed only by model name. Two servers
using the same alias therefore shared restrictions: a rejection on one could silently remove
temperature, rename token limits, or change thinking/reasoning settings on the other. That could
alter results or make the otherwise compatible server reject the modified request.

Compatibility state is now keyed by the sent model and API endpoint. Request construction uses
the same pair. Clients targeting the same pair retain learned compatibility, including in-flight
requests retrying an older option, while separate endpoints retain their own settings.

Focused offline evidence:

- **10 failed in 2.38s** before repair: default/explicit original endpoints, temperature rejection,
  token-limit rename, thinking rejection, a replacement thinking value and reasoning rejection.
- Concurrency, fallback, cache and option-learning checks: **68 passed in 3.49s**.
  Changed client module strict Pyright: **0 errors**.
- The existing test that seeded the private thinking registry now uses the endpoint-aware key.

No live provider requests, full suite, frontend or release changes. Compatibility state is in memory;
no credentials, provider settings or saved model responses are rewritten.
