# Do not judge layouts when an entire vision phase failed

2026-10-26, based on main `c05a8930`, using actual CPU-model traces retained
from the local VLM loop. Qwen3.5-0.8B Q4_K_M, CPU only, five threads. No model
answers or purchase draws are manufactured for the following evidence.

## Reproduction from actual model output

`visit-free-json-1792976940115080456` has one valid entrance response and one
failed shelf judgment: the model copied the response schema, including on its
bounded retry. The visit still completed. Its saved engine metadata reports:

```json
{"planning":{"plans":1,"plan_errors":0},"glances":1,"errors":1}
```

The A/B experiment, VLM layout judge and venue comparison previously rejected
only when more than half of the combined entry and shelf calls failed. The
actual trace has one failure in two calls, so the quality gate accepted it even
though there was no usable shelf measurement. More successful entrance calls
could dilute that failure fraction even further. The initial condition was
replayed against the current application helper before editing it; rejection
was false.

The shared phase check now blocks comparison when any attempted phase has zero
successful responses, in addition to the existing overall majority-failure rule.
It applies to A/B experiments, layout judging (including before calibration),
and venue synergy. A failed control/baseline stops before the remaining arms;
a failed candidate cannot produce a winning-layout or uplift report. Error text
names the unanswered phase. Partial-failure notes now correctly distinguish
fallback entrance plans from skipped shelf glances.

Zero attempted calls are not failed measurements. Browse-only visits, an
intentionally disabled phase, genuine no-choice responses and partial failures
with usable responses remain allowed under the existing overall threshold.
Ordinary saved visits are not deleted or rewritten; this change governs the
comparative studies' quality decisions.

`phase-quality-from-real-cpu.json` contains the recorded gate replay:

| Actual artifact | Failed / total | Previously rejected | Now rejected |
| --- | ---: | --- | --- |
| `visit-free-json-1792976940115080456` | 1 / 2 | No | Yes: shelf glances |
| `visit-free-json-1792977273489062712` | 0 / 2 | No | No |
| `visit-free-same-sku-json-1792978802063733908` | 0 / 2 | No | No |
| `visit-browse-baseline-json_schema-1792976452893202920` | 0 / 1 | No | No |

The first two model runs were measured in the preceding investigations; replaying
their quality metadata is not a new model execution. The new `free-same-sku`
full-visit case takes two actual calls and 16.80 seconds: a zero-price placement
and a 5,000-won placement share the same name and SKU. It buys one free unit,
checks out for zero revenue and respects inventory. Its entrance list is still
empty, so its semantic diagnostic remains failed. The comparison-quality check
does not claim to detect semantic errors in otherwise valid model decisions.

## Additional decoding experiments withheld

The original profile prompt at temperature 0 produces more repeated sentences,
invented age/gender and invented 10,000–20,000-won spending
(`profile-draft-night-temperature-zero-json_schema-1792978413728907426`, one
call, 17.96 seconds). Its failing exit stopped that shell batch, so the planned
zero-temperature bookstore call was not run.

A scratch presence penalty of 1.5 reaches the actual HTTP request and eliminates
exact sentence repetition in the two tested profile drafts. However,
`profile-draft-night-presence15-json_schema-1792978538661389933` invents family
visits, hospital rooms and 3,000–5,000-won spending (3.31 seconds), while
`profile-draft-bookstore-presence15-json_schema-1792978544887110418` invents
demographics and Tuesday-morning visits despite evening-only hours (4.05
seconds). Both use the original temperature 0.5. These decoding changes are
withheld; no sampling defaults or profile prompts change.

## Integration and release state

Integrated upstream `f30e7810`, including hover titles for clipped shopper names
and interview themes, plus the v0.8.0 preparation notes/home label. Release-note
wording describes concrete layout/accessibility improvements and the structured
local-model fixes, without claiming every possible screen/state is accessible
or all model facts are correct. At the release check, the latest published
release is still v0.7.0, with four platform assets; preparation is not publication.

Verification: the focused pre-fix run has 16 failures and 41 passes. After the
change, 102 affected backend tests pass (34.58 seconds), strict Pyright reports
zero errors/warnings, and the server import smoke check passes. The affected
interview suite has three passing frontend tests (3.09 seconds); TypeScript is
clean and changed-file lint has zero errors/two existing Fast Refresh warnings
in the home route. The production build passes (20.20 seconds), retaining the
usual chunk-size and Babel-plugin timing warnings. Whitespace checks pass.
