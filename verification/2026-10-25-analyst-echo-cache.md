# Run analyst question-echo recovery — 2026-10-25

An analyst reply that copied the current or a recent manager question passed the
answer schema, entered the response cache and was saved as a completed answer.
All 40 new SDK cases reproduced the gap before the fix (2.87s).

The request's response schema now rejects question-only echoes before caching,
using Unicode NFKC, case folding and punctuation/spacing normalization. The
existing two-attempt structured retry receives corrective feedback. A terminal
echo produces a useful error and leaves the saved conversation unchanged; a later
manual retry can reach the provider. Answers that quote a question and then give
an answer remain allowed. Fact filtering and output budgets are unchanged.

Validation: 78 focused tests passed in 10.27s. Coverage includes real intercepted
OpenAI-compatible and native Ollama SDK transports, JSON/JSON-schema, current and
previous questions, punctuation/fullwidth variants, cache reuse and invalid cache
revalidation, API persistence/retry, thread locks and project lifecycle. No live
inference. Full backend Pyright: 0 errors, 0 warnings; server boot passed. There
were 43 existing LiteLLM async logging cleanup warnings.
