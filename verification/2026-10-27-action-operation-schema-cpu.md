# Give local models an operation-specific shopping action schema

The preceding CPU investigation found a native-schema response repeating
79 anonymous `nav=area` rows until the 3,000-token output limit. The old
schema required navigation but made the actual action optional. Simply
requiring an action stopped that repetition in one candidate run but lost
the requested purchase, so that candidate was withheld.

The transmitted action schema now describes each operation separately.
Move and browse require a target; buy requires a supplied offer code and
quantity; wander requires its navigation and matching coordinates. Other
operations omit irrelevant fields, and non-wander navigation is derived
by the existing normalization. Empty catalogs cannot emit native purchases.
Prompts request actual records and omit irrelevant/default fields. There is
no action-count cutoff or forced purchase. Canonical Pydantic validation
remains compatible with existing actions and caches, including legacy raw
SKUs and the executor's quantity clamp for non-enforcing providers.

## Actual CPU evidence

Qwen3.5-2B Q4_K_M, llama.cpp b11878, five CPU threads, no GPU, context 8192,
reasoning disabled and temperature zero. These are text tasks on a
vision-capable model. All runs use fresh application caches and report zero
cache hits. Server prefix caching can still affect timing.

| Run | Mode | Completed HTTP responses | Seconds | Observed result |
| --- | --- | ---: | ---: | --- |
| Previous schema, buy one | Native | 1, then interrupted retry | 137.88 for first response | 79 anonymous rows; truncated; failure |
| Required-action-only candidate | Native | 1 | 19.16 | No requested purchase; withheld |
| Operation-specific candidate, buy one | Native | 1 | 20.29 | Exactly one Green Tea and exit |
| Candidate, browse only | Native | 1 | 9.71 | No purchases and exit |
| Candidate, absent laptop | Native | 1 | 9.63 | No purchases and exit |
| Candidate, free tea | Native | 1 | 17.64 | Exactly one free Green Tea and exit |
| Candidate, buy one | JSON | 1 | 29.23 | Purchase check passes; narration/route limitations remain |
| Final production, buy one | Native | 1 | 17.45 | Exactly one Green Tea and exit |
| Final production, buy one | JSON | 1 | 30.10 | Exactly one Green Tea and exit |
| Final production, full paid visit | Native | 3 | 34.37 | Correct receipt; impulse duplicates purchase |
| Final production, full free visit | Native | 3 | 41.81 | Correct receipt; impulse duplicates purchase |

The two full visits exercise real pattern selection, intent, impulse,
routing and receipt execution. Both end with one Green Tea, one payment,
exit, the correct total (250 minor units or zero) and no invalid buys.
However, each raw impulse response proposes a second Green Tea. Existing
budget/product-count enforcement removes it. These are execution passes
and model-semantic failures, not overall successful model visits. The paid
run was originally recorded before the probe distinguished those checks;
its separate `review.json` records the stricter interpretation without
altering the original response. The probe now requires both checks.

This demonstrates removal of the observed repetition in the selected
cases, not a general timing or semantic-accuracy guarantee. Some browse
coordinates and narration remain inaccurate; offer resolution repairs buy
placement. The JSON candidate still narrates in Korean. The duplicate
impulse purchase is the next investigation target.

## Verification and artifacts

The core schema and catalog checks pass 215 tests in 13.49 seconds. Final
checks across sixteen related files pass 756 tests in 29.01 seconds, with
14 existing LiteLLM coroutine warnings. Strict Pyright reports zero errors
and warnings; server import, probe compilation and diff checks pass.
Coverage checks usable operation shapes, required purchase fields, quantity
bounds, empty catalogs, malformed coordinates, irrelevant and engine-only
fields, cache round trips and legacy responses. Frontend code is unchanged;
frontend validation is inherited from integration 434.

Run `verification/local-intent-probe.py --case one --mode json_schema`;
add `--full` to exercise the complete pipeline and receipt. Inputs and raw
responses are retained under `/workspace/scratch/intent-operation-fields-`:
`candidate`, `final`, and `full`. The previous-schema truncated run is
`intent-output-final/one-json_schema-1793073519628174831`; it includes its
interruption record. The required-action-only rejected candidate is under
`intent-required-action-candidate`. No release asset is changed: this is
an Unreleased correction after v0.8.2.
