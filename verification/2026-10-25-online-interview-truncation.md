# Recover explicitly truncated online interview answers

The new post-visit interview retried structured answers with the same 700-token
limit. A local provider reporting an output cutoff therefore failed the question
without the budget recovery already used for browser decisions and exit surveys.

A terminal IncompleteOutputException, direct or the last failed Instructor
attempt, now gets one extra round at 1400 tokens. Prompt, seed and the existing
two-attempt structured-answer limit remain fixed. Non-cutoff errors propagate
without expanding the budget; failure of the larger round still reaches the
application error response and does not append a partial transcript.

A real LiteLLM/Instructor harness intercepts native Ollama and OpenAI-compatible
HTTP for JSON and JSON-schema modes. It covers recoverable/persistent cutoffs,
valid answers, misleading generated error phrases, HTTP 400/403/429, cache
contents, request budgets, seed/prompt stability, and direct/wrapped/earlier-only/
last-only terminal exceptions. Before repair, 12 new checks failed and 20 passed.

After repair, 47 focused tests passed in 7.53 seconds, including API conversations
and deletion/concurrency cases. Three existing asynchronous LiteLLM logging
warnings remain. Full-source Pyright reported zero errors and warnings; backend
boot passed. No frontend runtime, paid inference or downloaded weights changed.
The source fix was rebased onto the concurrently updated main technical report
commit 913931266bcf35d39e384d8863b514390b709d7b, preserving its PDF and figures;
that update changed no runtime code.
