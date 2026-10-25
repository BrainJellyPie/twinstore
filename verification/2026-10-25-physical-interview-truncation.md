# Recover terminal output cutoffs in physical-store interviews

The physical-store interview retried a cut-off answer at the same 700-token
limit. Unlike online interviews, it could not recover a local response that
needed a little more space to finish its JSON. Group interviews use the same
answer function and had the same limitation.

An explicit terminal IncompleteOutputException, direct or the final failed
Instructor attempt, now gets one additional round at 1400 tokens. Both rounds
keep the same prompt, seed, schema and two-attempt limit. Ordinary provider,
validation and echo failures do not trigger the larger budget. Repeated echoes
after a cutoff still reach the specific echo error and are not cached.

Extended the actual SDK cutoff matrix to physical trips: 12 new checks failed
and 20 passed before repair. Native Ollama and OpenAI-compatible requests cover
JSON/JSON-schema, recoverable/persistent truncation, misleading generated error
phrases, valid responses, HTTP 400/403/429 and cache contents. Direct/wrapped
exceptions verify that only the terminal cutoff triggers expansion. Added
cutoff-then-echo cases for both interview surfaces.

Validation: 168 focused tests passed in 14.30 seconds. The initial type check
identified a shared protocol in marketing reading that needed the optional
max_tokens parameter; its annotation was updated without changing its calls.
The final full-source Pyright check reported zero errors and warnings, and
backend boot passed. There were 55 existing asynchronous LiteLLM logging
warnings. No paid inference, model downloads or frontend runtime changed.
