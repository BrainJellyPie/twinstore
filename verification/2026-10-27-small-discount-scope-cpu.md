# Small-model discounts: failed candidates withheld

On main `4dc586192f08822955a294ea0e54e825306a886f`, Qwen3.5-0.8B
interpreted a Korean request for an extra 10% reduction of a 4,000-won selling
price as **-4000%** and added an unrequested shelf-wide change. Existing
validation rejected both attempts (9.38 seconds, two HTTP requests). The
application did not apply that invalid draft.

## Actual CPU comparison

Both models are Qwen3.5 Q4_K_M, using llama.cpp b11878, five CPU threads,
no GPU, 8192-token contexts and native JSON Schema. Layout probes use
temperature 0, seed 0, the existing 1500-token probe budget, normal validation
retries and a fresh application cache. No model replies were mocked. Server
prompt-prefix reuse was possible; timings are observations, not benchmarks.

| Candidate or control | Cases / HTTP | Result |
| --- | ---: | --- |
| Original 0.8B Korean extra discount | 1 / 2 | Repeated out-of-range -4000%, rejected |
| Explain money versus percentage | 1 / 1 | Correct individual discount, but also an unrequested shelf-wide cut |
| Add single-operation instruction | 1 / 1 | Same unrequested extra operation |
| Remove competing output examples | 9 / 9 | English/Korean extra discount and five other cases passed; free offer became 10% off, and a shelf edit changed unrelated products |
| Unchanged main, same two failed controls | 2 / 2 | Free offer and shelf edit both passed; the candidate failures are regressions |
| Short operation-focused prompt | 5 / 6 | Only free offer passed; wrong basis or invalid targets in the remaining cases |
| Restored main, 0.8B | 2 / 2 | Extra discount plus sign passed; fractional extra discount still failed |
| Restored main, 2B | 3 / 3 | Korean extra discount, fractional extra discount and extra discount plus sign all passed |

Total: **24 actual runs, 26 HTTP requests, zero application cache hits**.
All production prompt/schema candidates were removed. The layout engine is
byte-identical to main 462, SHA-256
`5f62885f783418546303c82b16c552a98e41be51576849efda280b5dab404422`.
The 0.8B discount problem is not claimed as fixed. Structurally valid drafts can
still change the wrong prices; readable JSON alone is insufficient evidence.
Model summaries also require review: the unchanged free-offer control applied
the correct price but described it imprecisely as removing a discount.

## Retained diagnostic coverage

`local-model-probe.py` adds two independent requests: 12.5% extra discount
($4 → $3.50, $5 reference retained), and a 10% extra discount combined with a
SALE sign on a different product. It compares all resulting product fields and
placements, and now records the loaded layout engine's path/hash and explicitly
checks source-store immutability. These cases may fail on smaller models; they
are not softened to accept the observed wrong answers.

Two cached replays of the passing 2B cases verify the final harness, including
source preservation. They are separate from the actual-inference count.
Backend application verification is inherited from unchanged main 462:
245 focused tests, strict Pyright and server boot passed. No backend source or
dependency changes are part of this integration.

## Concurrent branch integration

Merged `claude/online-shopping-features-ji7y0f` at
`609fb2719bacb1c4b7f162642ad84ec22bea303e`: localized percentages/distances and
concept-test price examples/hint layout. The published v0.8.2 tag and assets
are unchanged.

Frontend verification: 100 tests across 10 affected suites passed in 11.18
seconds; TypeScript and changed-file ESLint passed; Vite built in 20.91 seconds
with the existing chunk/plugin timing warnings. Probe compilation and diff
checks passed.

## Evidence

`/workspace/scratch/discount-scope-run-index.json` lists every actual result,
including failures. Candidate HTTP records retain exact prompts and replies.
Folders are `/workspace/scratch/{extra-discount-small-boundary,`
`discount-percent-prompt-candidate,discount-single-scope-candidate,`
`discount-without-examples-candidate,discount-without-examples-controls-small,`
`discount-small-unchanged-controls,discount-concise-candidate,`
`discount-restored-controls-8081,discount-restored-controls-8082}`.
Final harness replays are in `discount-probe-source-replays`.
