# Preserve local-model answer space when sending large starter catalogs

2026-10-26, based on main `15393c00`. A real Qwen3.5-2B Q4_K_M CPU run
used the production hypermarket template, 51 grouped rack sections, 154
allowed catalog categories, one product per category, and no alcohol.
The provider was llama.cpp b11878 with an 8,192-token context, five CPU
threads, zero GPU layers, and ordinary JSON output mode.

The initial category request consumed 8,045 input tokens. Although the
client requested up to 5,000 output tokens, the remaining context allowed
only 147: the model stopped midway through the section assignments with
`finish_reason=length`. Its retry stopped at the same point. The system
then decomposed the task. Several smaller replies had missing positions
or unknown categories such as `bake_ingredients`, so recovery required
further attempts and smaller batches. The broad run was deliberately
stopped after reproducing the issue and recording 11 completed HTTP calls
(278.994 s of recorded request time). It did not finish product selection;
no end-to-end success or final failure is claimed for that interrupted run.

The fix changes only JSON serialization at the starter-selection request
boundary: use compact separators instead of inserting spaces after every
comma and colon. Keep every rack, category label, product, exclusion,
limit, and owner instruction. This also covers correction and smaller-task
payloads, since they use the same request boundary. No choices are guessed
and no validation is relaxed.

Using the server's actual chat template and tokenizer on the captured
request reduced input from 8,045 to 6,960 tokens, leaving 1,232 tokens for
an answer. A fresh CPU call through the production category validator
then completed in 81.12 s total / one HTTP call, with 674 output tokens.
All 51 rack IDs appeared exactly once, with known category IDs and no
excluded categories. The parsed input values, system prompt, schema,
and model settings match the original request exactly; only JSON spacing
changed. The category-stage diagnostic intentionally stops before product
selection. This is evidence for context handling and complete assignments,
not proof that every selected department is semantically appropriate or
that the full large-store setup finishes in 81 seconds. Cache/prompt-prefix
conditions differ, so these times are observations, not a benchmark.

Artifacts under `/workspace/scratch/cpu-vlm-probe-2b/`:

- `hypermarket-json-1792991810511835257/http.jsonl` and `observation.json`
- `compact-categories-1792992105964588397/http.jsonl` and `result.json`

This integration also includes `b1688abd` from
`claude/blissful-rubin-tgy6gh`: online visitors can pause between pages
without spending their active patience budget. Four integration checks
compare identical visitors with zero versus very large pauses, across
short/normal visits and reminder settings. Choices, purchases, active
survey evidence and outcomes must stay identical; recorded clocks include
the pauses. The feature does not change model-generated decisions.

Verification: 1,327 affected backend tests passed in 54.14 s, covering
starter selection, repairs, cache reads, quotas, capacity, API application,
and online sessions. Six screenshot-crawl cases were excluded because no
rendering code changed. Six existing LiteLLM logging-worker coroutine
warnings appeared; no test failed. Strict Pyright reported zero errors and
warnings, and the backend import smoke passed. No frontend files changed
and the full repository suite was not run.

A subsequent complete compact-convenience-store run on the published fix
used the same actual 2B CPU model in JSON mode: two HTTP calls, no application
cache hits, 97.90 s total. It kept all ten suggested section categories and
filled all twelve physical racks with valid catalog products; final geometry
validation reported no issues. Artifact:
`/workspace/scratch/cpu-vlm-probe-2b/compact-json-1792992360172482068`.
This complete small-store check is separate from the category-only large-store
experiment. The invalid ID in the earlier large-store retry was
`bake_ingredients`; `baking_ingredients` is a valid catalog ID.
