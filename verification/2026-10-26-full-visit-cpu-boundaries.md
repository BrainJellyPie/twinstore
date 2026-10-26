# Full visits with the actual CPU VLM

2026-10-26, based on main `edfae234`. Qwen3.5-0.8B Q4_K_M with the F16
vision projector, llama.cpp b11878, CPU only, five threads, 8192-token context,
temperature 0. Initial probes use a 320-token entry request and a 400-token
shelf request; the final harness aligns the client and engine at 160 shelf
tokens, with the production one-time 320-token retry for truncation. The server stays running between examples; fresh application
caches do not imply cold server prefixes. Times are observations, not benchmarks.

`verification/local-visit-probe.py` runs `PerCustomerSimulationRunner` with the
real `VLMGlanceEngine`, rendered entrance and shelf images, action execution,
checkout and shared inventory. It does not mock model answers or force purchase
choices. HTTP tracing only records requests and responses, without headers or
credentials, and saves the actual image bytes sent to the model. Receipt,
customer, entry-plan, glance and inventory results are saved separately.

Run from the repository root with the local vision server on port 8081:

```bash
PYTHONPATH=backend/src backend/.venv/bin/python verification/local-visit-probe.py \
  --case stock-one --output /workspace/scratch/cpu-vlm-probe
```

Cases cover two customers competing for one unit, two placements of the same
SKU at $1 and $50, a free KRW offer, browsing without a shopping list, an
unavailable-only purchase intent, and a zero default planning cap. `--seed`
changes the simulation seed; `--structured-output json` exercises the plain JSON
transport. `--cache-from` is an explicit diagnostic replay and is reported as
such; it is not a new model measurement.

The probe separates transaction invariants, scenario coverage, and observed
model mistakes. A completed visit is not enough to pass. In particular, a water
purchase intent with an empty entry plan is flagged even if a later impulse draw
buys water. `units_before_shared_stock` includes both planned and impulse buys;
`entry_plan_lines` describes the model's entrance list. No-purchase cases disable
shelf glances so their entry decisions are isolated. These six synthetic cases
are diagnostics, not an estimate of model accuracy across real shoppers.

## Production behavior

Artifacts are under `/workspace/scratch/cpu-vlm-probe/`; raw traces and model
weights are not committed.

| Case / artifact directory | Calls | Seconds | Observed result |
| --- | ---: | ---: | --- |
| `visit-stock-one-json_schema-1792975790874720233` | 4 | 17.25 | Both shoppers say they need water but emit `items: []`; only one impulse purchase, so stock competition is not exercised |
| `visit-browse-baseline-json_schema-1792976452893202920` | 1 | 5.13 | Enters to browse, no purchase; passes |
| `visit-unavailable-json_schema-1792976733900950907` | 1 | 5.39 | Says there are no laptops, yet enters despite laptop-only intent; fails model check |
| `visit-free-json_schema-1792976741862326403` | 2 | 13.19 | Empty entry list despite explicit free-water intent; impulse purchase correctly costs zero; model check fails |
| `visit-same-sku-json_schema-1792976757507356194` | 2 | 11.54 | Empty entry list; later selects and pays the $1 offer within budget; model check fails |
| `visit-plan-disabled-json_schema-1792976771631447697` | 2 | 11.90 | Empty entry list with planning cap zero; one later impulse purchase, as permitted; passes |
| `visit-free-json-1792976299165840359` | 2 | 21.50 | Empty entry list, then the shelf response copies JSON Schema `properties` instead of giving a measured interest; no purchase |

The unavailable-only response is explicitly contradictory:
`{"enter":true,"items":[],"reason":"She wants a laptop, but the store has no laptops"}`.
The free shelf image was inspected directly: its price tag is `#1 0원` and its
product label is `Mineral Water 500ml`. The free purchase is one physical unit
with zero revenue, not a fabricated positive sale. The tested receipts, checkout,
exit and stock bounds pass; that does not make the model decisions correct.

The first stock probe had a diagnostic typo (`Action.CHECKOUT` instead of
`Action.PAY`) after saving the real outputs. It was corrected. Replay
`visit-stock-one-json_schema-1792976726221942434` uses four cached responses and
zero new HTTP calls, correctly reporting the omitted plans and incomplete stock
coverage. A later draft of the diagnostic read a nonexistent `GlanceRecord.error`;
it now checks the record's actual `outcome == "error"`. Neither issue was an
application failure. A first zero-cap fixture also specified `basket_size=1`,
which intentionally overrides the default cap. The final zero-cap fixture uses
an unspecified basket size; no application cap semantics were changed.

The final 160-token shelf harness repeats both important failures:
`visit-stock-one-json_schema-1792976928024104284` takes four real calls and
9.71 seconds, still with zero entrance-list lines and only one attempted unit.
`visit-free-json-1792976940115080456` takes three real calls and 25.14 seconds:
the 160-token schema echo is truncated; the normal 320-token retry completes
another schema echo with no measured interest. Both diagnostics exit with failure.
This final repeat also corrects the initial client/engine output-cap mismatch;
the original 400-token results above are retained and labelled, not overwritten.

## Prompt experiments withheld

Adding required mission/items fields to the wire schema still produces empty
lists. A prose consistency instruction also leaves both purchase lists empty.
Both are withheld.

A rewritten prompt with a concrete tea-purchase JSON example produces correct
water plans: `visit-stock-one-plan-example-json_schema-1792976280651393401`
uses four calls, 15.90 seconds, two attempted units before shared inventory,
one sold unit, one lost unit, and $1 revenue. A different simulation seed also
passes (`visit-stock-one-json_schema-1792976475434379812`, 14.95 seconds).
However, the same prompt turns away a browse-only shopper that the original
prompt admits. The favorable stock result is not sufficient to ship it.

Two more variants preserve the original instructions and add browsing, then
walk-out examples. Stock and browse cases pass, but the laptop-only shopper
buys water. The three-example free case correctly handles one free physical unit
(`visit-free-three-examples-json_schema-1792976625873579643`, 12.30 seconds),
which does not compensate for the unrelated purchase regression.

Adding an explicit browse JSON example to the rewritten prompt still turns the
browse-only shopper away (`visit-browse-complete-plan-json_schema-1792976680167508742`).
The complete-prompt stock case passes and its unavailable case correctly leaves.
All these prompt variants are withheld. Production entry prompts, response
schemas and purchase probabilities remain as at the starting main commit.
The committed addition is the reproducible full-visit diagnostic, with failures
retained rather than changing the shopper or purchase draws to make it pass.

## Integration

Also reviewed and integrated upstream `01235fa4`: light-mode status contrast,
playback progress naming, a valid hardware definition list, a keyboard shortcuts
sheet, and 15-minute arrow-key playback seeking. The changelog describes the
concrete accessibility changes without asserting every page and state is compliant.

Verification: 93 frontend cases in five affected suites pass (6.19 seconds),
TypeScript reports no errors, and the production build passes (20.98 seconds).
Changed-file lint has zero errors and one existing Fast Refresh warning in the
root route; the usual chunk-size and Babel-plugin build warnings remain. The
probe passes Python compilation and whitespace checks. No backend application
source changes remain, so strict backend typing and backend tests are not repeated.
