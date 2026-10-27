# Shopper-search clock semantics: candidate withheld

Extend the actual-model probe with shifted second boundaries, a before-only
condition and a minute-only control. Compare both customer IDs and applied
criteria. Treat `HH:MM` and `HH:MM:00` as equivalent boundaries while keeping
nonzero seconds distinct. Matching IDs with additional unrequested conditions
still fails. Production prompts, validation, matching and caching are unchanged.

The existing prompt and field descriptions ask for HH:MM even though the
matcher accepts seconds. A candidate explicitly allows HH:MM:SS and asks the
model to preserve seconds. It improves the observed clock text in the two
bounded second-precision queries, but **none of its six runs passes the whole
semantic check**. It is withheld rather than presented as a working search fix.

All ten runs use Qwen3.5-2B Q4_K_M with llama.cpp b11878, five CPU threads,
no GPU, context 8192, reasoning off and temperature 0. This is a text task
on a VLM, using seven complete synthetic personas and recorded synthetic
visits, not real customers. All runs use fresh caches and actual inference:
13 HTTP requests, zero application cache hits, no mocked or replayed replies.

| Version / request / output mode | Seconds | Requests | Observation |
| --- | ---: | ---: | --- |
| Parent / 15:00:30–16:00 / native schema | 24.15 | 2 | seconds omitted; invalid shelf dependency rejected |
| Parent / 15:00:30–16:00 / JSON | 19.64 | 1 | seconds omitted; extra shelf/product conditions; wrong IDs |
| Candidate / 15:00:30–16:00 / native schema | 24.41 | 2 | seconds retained; invalid shelf dependency still rejected |
| Candidate / 15:00:30–16:00 / JSON | 19.24 | 1 | correct IDs, but extra shelf condition |
| Candidate / 15:00:29–15:00:31 / JSON | 8.08 | 1 | correct IDs and seconds, but extra shelf condition |
| Candidate / 15:00:29–15:00:31 / native schema | 28.64 | 2 | seconds retained; invalid shelf dependency rejected |
| Candidate / before 15:00:30 / JSON | 18.99 | 1 | reverses before to after; extra shelf/product conditions |
| Candidate / 15:00–16:00 / JSON | 8.38 | 1 | correct clock fields, extra purchase conditions exclude a nonbuyer |
| Parent / before 15:00:30 / JSON | 19.79 | 1 | same inversion and extra conditions as the candidate |
| Parent / 15:00–16:00 / JSON | 9.33 | 1 | same extra purchase conditions as the candidate |

The parent controls show that the before/after inversion and minute-window
purchase constraints already exist; they are not demonstrated regressions
from this candidate. Conversely, keeping seconds or getting the expected IDs
in two fixtures does not establish semantic correctness. Failed native
dependencies remain uncached and bounded by the existing retry limit.

Artifacts use `/workspace/scratch/shopper-clock-baseline/`,
`shopper-clock-candidate/` and `shopper-clock-parent-controls/`. Exact paths,
criteria, errors and timing are in `shopper-clock-summary.json`; the withheld
production diff is `shopper-clock-candidate.patch`. The extended probe compiles
and diff checks pass. No production/backend/UI checks are rerun for this
diagnostic-only change; prior integration 428 and fix 427 checks still apply.
