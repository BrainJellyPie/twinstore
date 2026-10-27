# Validate generated shelf stops independently of purchase conditions

Two actual CPU requests for visitors to the unavailable Ice cream freezer
produce `stopped_at=["Ice cream freezer"]` with `bought_there="any"`. The
previous dependency check only validates a shelf when a purchase condition
is present. Matching then discards the unknown shelf, applies `Everyone`
and returns all seven customers. Both requests reproduce this behavior:
6.98 and 7.66 seconds, one HTTP request each.

Any nonempty generated `stopped_at` list now requires at least one resolvable
shelf before caching or matching, regardless of purchase conditions. Missing
lists stay unrestricted; mixed known/unknown alternatives retain the known
matches and existing warnings. Duplicate shelf names still resolve to all
their rack IDs, and copied names with case/quote variations remain usable.
The existing purchase-dependency check still catches a missing shelf list.
The production prompt/schema and direct legacy `apply_filter` behavior do
not change.

The expanded shelf tests fail **15 cases and pass 70 in 4.32 seconds** before
the production change. The final nine-file run passes **535 tests in 12.85
seconds**, with 115 dependency/resource warnings. It covers both HTTP output
modes, corrected/repeated replies, old invalid cache entries, later recovery,
blank and ambiguous targets, empty stores, duplicate names and existing
product/time/spending filters. Strict Pyright reports zero errors or warnings;
application import, probe compilation and diff checks pass. An initial test
parameter-list syntax typo caused collection failure; it was corrected before
the stated failing run and was not an application failure. UI checks inherit
integration 432.

## Fresh CPU results

Qwen3.5-2B Q4_K_M runs through llama.cpp b11878 with five CPU threads, no GPU,
context 8192, reasoning off and temperature 0. These are text requests to a
VLM over seven complete synthetic personas and synthetic visits. All six
runs are fresh: nine actual HTTP requests, no mocked/replayed replies and
zero application cache hits.

| Version / request / output mode | Seconds | Requests | Result |
| --- | ---: | ---: | --- |
| Parent / explicitly unavailable shelf / JSON | 6.98 | 1 | all seven customers; shelf condition dropped |
| Parent / named unavailable shelf / JSON | 7.66 | 1 | all seven customers; shelf condition dropped |
| Final / explicitly unavailable shelf / JSON | 49.39 | 2 | first target rejected; correction reaches output-token limit; no match result or cache |
| Final / named unavailable shelf / JSON | 15.16 | 2 | repeated unknown target rejected; no match result or cache |
| Final / known Tea shelf / JSON | 9.87 | 1 | valid shelf, but unrequested demographic, persona and purchase filters; wrong empty result |
| Final / known Tea shelf / native schema | 24.29 | 2 | missing shelf with purchase condition rejected by existing dependency check |

For both unavailable-shelf cases, the first final request and reply exactly
equal the baseline. The new validation prevents those observed replies from
widening the search to everyone. The two bounded failures are rejection of
unusable criteria, not successful searches or proof that the model repaired
its meaning. The known-shelf controls still fail semantic checks, so there
are **zero complete semantic passes**. Extra valid-looking criteria and
slow correction responses remain unresolved model limitations.

Artifacts are under `/workspace/scratch/shopper-stop-baseline/` and
`shopper-stops-final/`. Exact paths, timings, errors and cache-file counts are
in `shopper-stops-final-summary.json`; first-request/reply comparisons are in
`shopper-stops-reproduction.json`. Test/check logs and file lists use the same
prefix. Reproduce with `missing-shelf`, `named-shelf` and `known-shelf` in
`verification/local-filter-probe.py`.
