# Recover an online shopper's truncated decision

The newly integrated online model policy fell back to a rule decision immediately
when its 240-token answer was cut off. The physical-store vision policy already
allows a bounded larger answer in this situation. Online text and vision shoppers
now retry once at twice the initial budget, only for a typed terminal
`IncompleteOutputException` (including Instructor's final wrapped attempt).

The retry preserves the page, options, prompt, image, shopper route and seed.
It does not change the client's configured ceiling or cache an incomplete answer.
A second cutoff still falls back to rules. Validation failures, generated text
mentioning token limits, and HTTP 400/403/429 do not increase the budget.

Scripted local HTTP responses exercised the real LiteLLM/Instructor paths through
both OpenAI-compatible and native Ollama protocols, both JSON modes, and text/image
decisions. Before repair, 22 cases failed and 18 controls passed in 3.05 seconds.
The final expanded regression file passed **64 cases in 3.18 seconds**, including
the HTTP negative controls. Related online sessions, physical VLM cutoff handling
and native Ollama cutoff/cache tests also passed: **161 distinct focused cases**
across final runs. Full-source Pyright reported **0 errors and 0 warnings**.

An intermediate test incorrectly expected an HTTP seed with seeding disabled;
the fixture now enables the existing `seed=0` configuration. This was a test
setup error, not a product defect. Existing LiteLLM logging coroutine warnings
remain (15 in the final regression run). No native inference or paid calls were
used; this validates recovery and protocol behavior, not model answer quality.
