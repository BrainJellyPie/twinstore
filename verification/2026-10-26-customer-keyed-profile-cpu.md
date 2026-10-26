# Give a small model a finite trade-area profile to fill

2026-10-26, based on main `f5beac1d`. Real CPU runs use Qwen3.5-2B Q4_K_M,
llama.cpp b11878, five threads, zero GPU layers, and an 8K context. These
customer-generation requests are text-only calls to the vision-capable model.

A French cafe case with a EUR 2.50–7.75 budget failed before customer writing:
the first trade-area request timed out at 180.25 s. One model request was
attempted; no complete HTTP response was received, so the probe's completed
HTTP count and token usage were zero. Those zeros do not mean no work ran.
The original probe artifact is `persona-fractional-json-1792992494019850872`.

A separate diagnostic retained the production profile prompt/schema and used
a 1,000-token output limit with one attempt. In 42.54 s it captured a response
ending with `finish_reason=length`: the model wrote its keywords, extended
identities beyond the requested size, and repeated `serving` dozens of times
without ever closing the identities array or writing purposes. This shorter
diagnostic demonstrates repetition; it is not a complete response recovered
from the earlier timeout. Artifact:
`profile-bounded-persona-fractional-json-1792992764850229891`.

The profile wire format now has numbered string-valued fields: eight
keywords, sixteen identities, and sixteen purposes. These target sizes fit
the old prompt's 5–10 / 15–30 / 15–30 ranges. Numbered objects give the model
explicit final keys; the schema and prompt describe the same structure.
The harness requires the complete expected key set and restores numeric
order before validating the values. It rejects missing/extra keys, nulls,
nontext values and schema definitions rather than manufacturing labels.
The existing blank/duplicate cleanup remains after validation.

Stored models and caches still contain ordinary lists. Legacy list-valued
responses remain valid, including their existing 20/40/40 maximum lengths
and 120-character label bounds. No numbered keys enter customer identities
or downstream UI data. The changed schema/prompt also change cache identity.

An initial scratch version completed the profile in one actual JSON-mode
call (28.29 s), but contained vague person labels and weakly grounded purposes;
that was format evidence, not a semantic-quality pass. The final production
version then ran all three stages of the French case in 65.49 s / three HTTP
calls, no application cache hits. Its profile stage completed in 28.946 s.
Customer writing finished, and EUR 2.50–7.75 became exactly 250–775 stored
units for the first person. The second person still received 0–0, despite
the supplied budget. The whole probe therefore remains **failed** on source
budget preservation. This change fixes the reproduced profile repetition,
not the outstanding customer-budget or narrative-grounding problems.
Artifacts: `keyed-profile-1792992941341670476` and
`persona-fractional-json-1792993171088233185`, under
`/workspace/scratch/cpu-vlm-probe-2b/`.

The new regression cases had five failures and 21 passes before the change.
They exercise JSON and JSON Schema over the real SDK with an offline HTTP
transport, reversed object key order, canonical cache reuse, missing/extra
keys, schema echoes, invalid values, old list responses, Unicode blanks,
duplicate cleanup and retained length limits. The focused new/label-bound
checks pass (56 cases). These deterministic tests do not replace the actual
CPU observations above.

The Japanese-category case also completed all three production stages using
JSON Schema (44.86 s, three actual calls, zero application cache hits). It
retained the exact Japanese category values. Its full probe likewise failed
because the second customer's budget was 0–0. Manual review additionally
found a 40s persona described as a senior citizen. Artifact:
`persona-local-categories-json_schema-1792993265096853908`.

The affected backend selection ran 897 cases: 891 passed and six failed
because the existing empty-pool fixtures still asserted the old array wire
schema. Those fixtures now check the required numbered keys and supply
numbered objects for their enforcing-provider case; non-enforcing-provider
cases continue returning legacy/empty arrays. The ten empty-pool checks
then passed on rerun. No production changes followed the larger run, so
all 897 selected cases have a passing result without repeating the entire
selection. The larger run emitted 13 LiteLLM logging-worker coroutine
warnings. Strict Pyright reported zero errors/warnings and the backend
import smoke passed. No frontend files changed or full repository suite ran.
