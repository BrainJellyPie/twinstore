# Keep echoed questions out of the interview response cache

Interview echo detection ran after the structured client cached its response.
When both answers repeated a question, retrying the same question reused both
invalid cached answers and failed without contacting the model, even after the
provider recovered. A successful automatic retry also left its rejected first
answer in the cache.

The per-question response schema now rejects current or earlier interviewer
questions before successful-response caching. Instructor's existing two-attempt
budget supplies corrective feedback to the model. Persistent echoes keep the
specific user-facing error. The prompt explicitly asks for an answer to the
latest question. There is no additional outer echo retry; terminal output
cutoffs still get the existing bounded 700-to-1400-token recovery round.

All 32 new actual LiteLLM/Instructor HTTP cases failed before repair. They cover
native Ollama/OpenAI-compatible providers, JSON/JSON-schema modes, enabled and
disabled provider seeding, a recoverable echo, persistent current/earlier echoes,
and case/punctuation variations. A fresh client can retry a failed question;
only valid answers are cached and reused. Injected invalid cached entries are
revalidated and replaced. Retry requests contain the corrective instruction.
The lightweight model double now honors structured validation retries, which
are exercised end to end by this SDK matrix.

Validation: 87 focused interview, lifecycle and cache tests passed in 8.24
seconds. Full-source Pyright reported zero errors and warnings; backend boot
passed. There were 27 existing asynchronous LiteLLM logging warnings. No paid
inference, model download or frontend runtime change was needed.
