# Request complete customer batches from local grammars

The customer prompt asks for one person per specification, but its transmitted
schema allowed a batch to end after one person. That response is accepted for
compatibility with non-enforcing providers; full generation then fills the rest
of the population with twins. A grammar-following local model could therefore
underfill a request while satisfying every schema rule. Separately, a caller's
batch size above twelve could request more people than the response model accepts.

Each request now advertises identical minItems and maxItems equal to its actual
specification count. Runtime validation retains the existing one-to-twelve range
and short/surplus handling. Request batching and write-plan estimates both clamp
the chosen batch size to one through twelve, so no specification is skipped by a
larger configured batch. The existing bounded split on context rejection or output
truncation uses the child's exact count automatically. No retries were added.

Before the patch, 15 targeted regressions failed and four controls passed. HTTP
tests inspect the transmitted limits for single, partial and complete batches,
sizes up to 25, and zero/negative direct-call sizes. A scripted minimum-length
grammar response demonstrates full 25-person generation with a probe, distinct
IDs, no twins, and accurate request estimates. Existing non-enforcing short and
surplus controls retain their results.

Focused customer grammar, evidence, context/truncation recovery, concurrency,
missing-day and write-choice checks: 153 passed in 8.90 seconds. One existing
LiteLLM logging-cleanup warning occurred. Strict Pyright: zero errors. No live
inference or model-specific grammar compiler was run; the evidence covers the
transmitted schema and pipeline behavior rather than model compliance quality.
