# Model event windows — 2026-10-25

The automatic situation writer accepted empty/reversed event hours, cached them,
and replaced the end with 24. A model's 18–18 event therefore became six hours
of increased traffic, while the manual scenario API correctly rejected it.
Draft events now inherit LocalEvent's same-day interval validation. The converter
preserves the validated hours exactly, and the prompt states the interval rule.
The existing describe-API fixture now supplies a valid 18–22 interval instead of
asserting silent widening. Overnight intervals remain unsupported, as in the
manual API; this change does not guess a replacement time.

Baseline: 36 failures and 4 passes in 3.42s. Final focused run: 301 passed in
8.14s, including native Ollama/OpenAI, JSON/JSON-schema, equal/reversed/overnight
hours, SDK correction, repeated failure without caching, and invalid legacy
cache recovery. Actual compiled traffic is limited to the corrected hours.
Midnight boundaries, full-day events, weekday restrictions, optional annotations,
choice spelling and API rejection passed. Full backend Pyright: 0 errors,
0 warnings; server boot passed. No live inference. Existing SDK logging cleanup
warnings remain.
