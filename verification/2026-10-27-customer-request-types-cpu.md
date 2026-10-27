# Preserve the type requested for each generated customer

The customer writer samples one or two allowed identity labels for every
individual request. Its previous validator only checked the containing
hour's complete identity pool. A response could therefore give a requested
night-shift worker the identity of a local resident from the same hour,
be accepted and enter the cache.

The writer now carries each row's selected labels alongside its clock and
prompt text, including through output/context splitting. It validates
returned identities against those exact labels before caching, and gives
correction requests the complete returned-row order and all mismatched
indices. It does not reorder or relabel generated people. Existing handling
of short/surplus responses and population twins is unchanged; this guard
applies to independently written request rows.

The initial production prompt and transmitted schema are unchanged. Raw
labels remain structured values in the validator: plus signs, commas,
Unicode and whitespace/case normalization do not require parsing the
human-readable request line.

## Actual CPU reproduction

An audit first found five mismatches among the twelve retained customers
in the earlier production-temperature run
`cpu-vlm-probe-2b/persona-default-temperature/persona-nightmarket-local-batches-json_schema-1793037128767461863`.
Those are previously recorded calls, not new inference. The broader audit
also included experimental traces, so its combined mismatch count is not
a production error rate. The audit script and detailed records are
`audit_persona_request_types.py` and `persona-request-types-audit.json`
under `/workspace/scratch/`.

A fresh five-person test reproduced the bug on current production. All
customers arrive at 23:00; requested types are worker, resident, worker,
resident, and either type for the fifth person. The first response instead
used resident, worker, worker, resident, worker. The first two mismatches
were accepted and cached before the fix.

Four fresh runs made **ten HTTP calls**, all with Qwen3.5-2B Q4_K_M on
llama.cpp b11878, five CPU threads, no GPU, 8,192 context, reasoning off,
temperature **1**, and zero application cache hits. This is a text task
for the local VLM; no model response was mocked or replayed.

| Run | HTTP calls | Time | Result |
| --- | ---: | ---: | --- |
| Five-person native-schema baseline | 1 | 35.61 s | Two row types wrong; accepted/cached; also has budget violations |
| First validator, reporting only the first wrong row | 3 | 142.68 s | Repeated type errors rejected; zero written customers and no cache entry |
| Final validator with complete row order, native schema | 3 | 158.75 s | Third response has all five identities in the correct rows; budget violations remain |
| Final validator, three-person JSON request | 3 | 97.78 s | Rejects nurse/student/retiree twice; accepts nurse/nurse/student with unspecified budgets on the third response |

The complete first request and response content of both five-person
validator runs are exactly equal to the baseline. The final correction
therefore exercises rejection of the recorded wrong labels, rather than
benefiting from a different first answer. Retries remain bounded at three;
these observations are **not a latency improvement**.

The five-person final response still assigns two residents budgets of
KRW 2,000–5,000 despite the supplied 3,000–10,000 range. Its overall probe
result is therefore a failure even though the identity error is repaired.
The three-person JSON run passes the probe's count, requested identity,
category, unspecified-budget and basic text checks. This does not establish
general narrative quality or solve the previously documented budget
interpretation failures.

`verification/local-model-probe.py` now includes `persona-nightmarket-five`
and checks individual requested types for all of its fixed-cohort writer
cases, using the actual request bodies. Reproduce with `--temperature 1`,
`--endpoint http://127.0.0.1:8082/v1` and the table's output mode.
Local raw input, request/response, customer and cache artifacts are under:

- `/workspace/scratch/persona-row-types-baseline/`: `1793065250351732201`.
- `/workspace/scratch/persona-row-types-final/`: `1793065466659647015`
  (the intermediate first-error-only validator, despite the directory name).
- `/workspace/scratch/persona-row-types-ordered/`: native
  `1793065867332183993`, JSON `1793066038001028770`.

`/workspace/scratch/persona-row-types-summary.json` records request/response
equality, all returned/requested labels, cache counts, timings and limits.

## Regression verification

The new regression file reproduced **50 failures and two passes** before
the fix (5.18 s). It tests both wire modes, correction/repeated failure,
invalid legacy caches, one- and three-person batches, nonzero sample
offsets, concurrent requests, raw labels containing delimiters/Unicode,
recursive splitting, and complete ordered correction guidance.

The first focused run passed 155 tests in 7.45 s. A label-vocabulary run
then exposed two old fixture failures: the fake writer cycled through the
global identity enum instead of following the actual request rows. It now
chooses an allowed label from each supplied row while retaining vocabulary,
order and cache assertions. The spelling-only fixture also fixes the
requested type so unrelated random sampling cannot affect its assertion.
The repaired label-focused run passed 133 tests in 8.75 s.

The final run passed **1,304 tests across 40 files** in 51.81 s. These are
the engine test files directly invoking the changed customer generation
functions, including budget, traffic, provider, batching and population
recovery checks. Its 37 warnings were dependency/resource-cleanup warnings.
Strict backend Pyright returned zero errors/warnings, backend import smoke
passed, and probe compilation and diff checks passed. The full repository
suite was not repeated.

No frontend production files changed, and the published v0.8.2 files and
changelog section remain unchanged.
