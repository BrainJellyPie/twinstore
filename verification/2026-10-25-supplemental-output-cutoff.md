# Reject truncated supplemental-data summaries

The raw text completion path returned content without checking its finish
reason. Unlike structured answers, a summary terminated by `length` could
become evidence in the customer-generation prompt. Even a complete-looking
sentence may be only the first part of a cutoff response.

Raw text now raises the existing IncompleteOutputException on a length finish,
after recording the request and reported tokens. The supplemental pipeline's
existing failure contract returns an empty summary, preventing incomplete
evidence from being saved or forwarded. This change adds no retries, changes
no normal final-answer parsing and does not alter the summary storage limit.
It does not add a new user notification or retry policy for unavailable data.

Thirty new tests pass through real LiteLLM HTTP handling for OpenAI-compatible
local servers and native Ollama. They cover empty cutoff content, incomplete
sentences, complete-looking sentences, leading thoughts, CSV and XLSX. The full
upload-to-summary-to-customer-prompt path excludes length-cutoff results and
retains the same content when the server reports normal completion. A failed
raw request is counted once, including its tokens, and does not trigger more
HTTP attempts.

Before repair: 18 failed, 12 passed in 3.46 seconds. After repair: 345 focused
summary, CSV, output-budget, retry-accounting and Ollama recovery tests pass in
9.42 seconds. Full-source Pyright reports zero errors and warnings. Tests emit
34 existing LiteLLM logging coroutine warnings. No full suite, model weights,
native inference or paid requests were used.
