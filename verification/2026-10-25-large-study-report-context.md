# Complete context for large study reports — 2026-10-25

A valid maximum-design conjoint study (six attributes, six levels each, prices,
120 respondents across demographic groups, long permitted labels) produced
16,332 characters of aggregate report JSON. The previous 16,000-character cut
ended inside the final notes, losing the caveats and leaving invalid JSON.

After dropping repeated quotations when needed, report context now stores
repeated table keys once as columns plus rows, starting with the largest saving.
Every value, row order and column identity is retained. The analyst prompt
explains this representation. The reproduced report is 13,237 characters with
all caveats intact. Small reports retain their existing representation and saved
source reports are untouched. If a very large imported scalar cannot be
compressed, complete JSON may exceed the 16,000-character target; provider
context errors remain visible rather than silently losing report evidence.

Validation: all 6 new cases failed before the change (4.39s); 15 focused tests
passed afterward (3.83s). These include real fitting with one bootstrap draw,
round-trip equality of every aggregate, native Ollama/OpenAI-compatible SDKs,
JSON/JSON-schema responses, caching, existing survey and study-reading APIs, and
an oversized scalar. No live inference. Full backend source Pyright: 0 errors,
0 warnings; server boot passed. Four existing LiteLLM logging cleanup warnings.
