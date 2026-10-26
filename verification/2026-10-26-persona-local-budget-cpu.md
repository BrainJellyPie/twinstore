# Probe actual local batch sizes and reject age-only profile repetition

The local generation pace is five customers per request. A fixed twelve-person
night-market cohort therefore exercises three actual writer requests (5+5+2),
independently of the traffic estimator. On main `f5e55dc6`, the production
prompt wrote all twelve records but **seven budgets violated the supplied
KRW 3,000–10,000 range**. Both lower and upper bounds were affected. Request
shape, cardinality, labels and arrival hours passed; this is a semantic
instruction-following failure, not a malformed-JSON failure.

The harness adds `persona-nightmarket-local-batches` for that production-sized
boundary while retaining `persona-nightmarket-batch` for a twelve-person
single-request stress case. Three prompt candidates were examined without
changing the production prompt:

| Actual run | Requests | Time | Outcome |
| --- | ---: | ---: | --- |
| Production prompt, 5+5+2 | 3 | 108.56 s | Seven budget violations |
| Explicit budget-copy candidate, 5+5+2 | 3 | 109.33 s | Checked budgets and repetition pass; its earlier twelve-person run duplicated four complete profiles |
| Copy budget fields but write other fields independently, twelve at once | 1 | 96.39 s | Budget/exact-duplicate checks passed, but five records differ only in introductory ages |
| Same candidate, 5+5+2 | 3 | 98.62 s | Checked budgets and repetition pass |
| Name the two budget fields explicitly, twelve at once | 1 | 88.42 s | Checked fields pass; manual review finds twelve descriptions and eleven intents/behaviors |
| Same field-naming candidate, 5+5+2 | 3 | 104.39 s | Two budget violations: 2,000–4,000 and 6,000–12,000 |

Every completed row used actual Qwen3.5-2B Q4_K_M CPU inference, native
`json_schema`, fresh application caches and zero cache hits. llama.cpp b11878
used five CPU threads, no GPU and an 8,192-token context. Server prefix reuse
was possible; times are not a speed comparison. These fixtures isolate the
customer writer from trade-area and traffic estimation.

The second candidate initially appeared green under exact-record matching.
Manual comparison found that it cycled otherwise identical profiles while
changing `42-year-old` to `43-year-old`, within the same structured age group.
The harness now flags that narrowly defined repetition too. It normalizes
only an introductory numeric age in the description and retains age group,
budgets, category choices and all remaining text. Family ages later in a
sentence and meaningful quantity/behavior differences remain distinct.
This is a bounded diagnostic, not a general semantic-diversity measure, and
it does not deduplicate or modify application customers.

A cache-only reanalysis of the second candidate's twelve-person response
correctly reports all five age-only repeats (zero HTTP calls, one cache hit).
Its five-person-batch positive control remains green (zero HTTP calls, three
cache hits). These replays are validation of the new check, not fresh model
evidence. Additional artifact and controlled-record checks confirm exact
duplicates are not counted twice and family ages/behavior differences remain
distinct. Probe compilation and diff checks pass.

The second candidate's plain-JSON run was stopped after the large-batch
regression became clear: one HTTP response completed, a second request was
interrupted, and there is no complete cohort result. Its later unspecified-
budget/USD controls were not run. The third candidate's control sequence
stopped on its first failing local-batch case. No JSON, unspecified-budget or
USD success is claimed for either interrupted/stopped sequence.

**All three prompt candidates remain withheld.** The production prompt,
batch size, budget values, deduplication and generated application data are
unchanged. Only the harness and this evidence record are committed; already
green application checks were not repeated. The budget limitation remains
open, and v0.8.2 is unchanged.

Artifacts under `/workspace/scratch/cpu-vlm-probe-2b/`:

- `persona-fixed-cohort-batch5/persona-nightmarket-batch-json_schema-1793024197587695697`
- `persona-budget-copy-batch5/persona-nightmarket-batch-json_schema-1793024388771445054`
- `persona-budget-fields-batch12/persona-nightmarket-batch-json_schema-1793024650994382949`
- `persona-budget-fields-local-native/persona-nightmarket-local-batches-json_schema-1793024903735831067`
- `persona-budget-bounds-batch12/persona-nightmarket-batch-json_schema-1793025605079530265`
- `persona-budget-bounds-local-native/persona-nightmarket-local-batches-json_schema-1793025849964061698`
- `persona-age-review-replay/persona-nightmarket-batch-json_schema-1793025313903909702`
- `persona-age-positive-replay/persona-nightmarket-local-batches-json_schema-1793025475454239467`

The earlier four-duplicate candidate is documented in
[the fixed-cohort investigation](2026-10-26-persona-fixed-cohort-cpu.md).
Scratch runners are `/workspace/scratch/probe-persona-budget-copy.py`,
`probe-persona-budget-fields.py` and `probe-persona-budget-bounds.py`.
