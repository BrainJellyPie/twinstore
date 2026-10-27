# Recover an omitted navigation mode in model actions

A real CPU JSON-mode intent request fails after two responses. The first
copies the response schema. The second supplies five actions, including
exactly one `@P1` Green Tea purchase, but omits `nav` in every row. Pydantic
rejects the entire response for the five missing navigation fields, despite
the usable purchase code and quantity.

Normalize only omitted navigation fields in generated intent/impulse actions.
An exit means `leave`; purchases and payments mean `path`, matching the
engine's existing execution rules. Enter, move and browse mean `path` when
no area was supplied. Explicit navigation modes are unchanged. Missing
action kinds, unknown kinds, wandering, ambiguous area movement, malformed
coordinates and explicitly invalid modes still need validation/correction.
The model's purchases, quantities, targets and narration are not invented or
replaced. Prompt text and transmitted JSON schemas are unchanged.

## Actual CPU evidence

Qwen3.5-2B Q4_K_M runs through llama.cpp b11878 with five CPU threads, no GPU,
context 8192, reasoning disabled and temperature zero. This is a text task
on a vision-capable model. The probe runs the production intent writer and
offer resolution, not pattern selection, impulse planning or a complete visit.

| Code / mode | HTTP responses | Seconds | Result |
| --- | ---: | ---: | --- |
| Before / JSON | 2 | 100.32 | Fails on five missing `nav` fields |
| After / JSON | 2 | 86.49 | Resolves exactly one Green Tea; no invalid purchase dropped |

Both request bodies and both reply messages are identical before and after.
Both runs use fresh caches with zero application cache hits. The initial
schema-copying response still occurs. The repair accepts the subsequent
usable answer; it does not reduce the number of model calls or establish a
general speed improvement. The reply also has misplaced per-action
`reasoning` extras and an imprecise narrative age, so passing the purchase
check does not establish narrative accuracy.

A separate native-schema check discovers another failure: the response
repeats `nav=area` 79 times without meaningful action kinds and reaches the
3,000-token limit after 137.88 seconds. Its second attempt was canceled to
avoid another prolonged repeated response. This is one completed HTTP
response plus one interrupted attempt, not a completed or passing native
case. The repeated-generation problem is separate from missing-navigation
normalization, which does not change the wire schema. It remains unresolved
in this change and is the next investigation target.

## Regression checks and artifacts

The initial focused tests reproduce **29 failures and 45 passes**. Final
checks across fourteen related files pass **644 tests in 22.56 seconds**,
with 14 existing LiteLLM coroutine warnings. Coverage includes both SDK
output modes, intent and impulse responses, canonical cache reuse, omitted
targets, preserved explicit navigation, malformed and ambiguous input,
purchase quantities, checkout insertion and final receipt amounts. Strict
Pyright reports zero errors and warnings; application import, probe
compilation and diff checks pass. Frontend code is unchanged and inherits
integration 434's checks.

Reproduce using `verification/local-intent-probe.py --case one --mode json`
against the CPU server. The baseline is
`/workspace/scratch/intent-output/one-json-1793073107027733958`; the repaired
run is under `intent-output-final/one-json-1793073387838931165`.
Input/reply equality is recorded in `intent-missing-nav-reproduction.json`.
The interrupted native case ends in `1793073519628174831` and includes
`interruption.json`, its original requests and the truncated reply. Test
logs and the selected file list use the `intent-missing-nav-` prefix.
The v0.8.2 release files are unchanged; this is an Unreleased correction.
