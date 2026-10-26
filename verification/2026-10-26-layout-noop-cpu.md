# Unsupported layout requests: diagnostic cases and withheld candidates

On main `57dcd38a`, the request to change only an absent Dragonfruit Juice
and leave every other product unchanged failed after two model requests
(17.45 seconds). The prompt/schema require at least one applicable operation;
the model repeatedly proposed a price operation for the absent product.
Existing validation refused it. No unrelated product was changed.

The reusable probe now includes an absent product in English and Korean,
an unsupported wall-painting request and an explicit request to keep every
price/sign/placement unchanged. It checks complete product state and requires
an explicit no-op response for those diagnostic cases. Current production
does not yet support that response: these cases can fail and are not claimed
as repaired. Existing positive cases retain their expectations.

## Investigation and decision

Qwen3.5-2B Q4_K_M, llama.cpp b11878, five CPU threads, no GPU,
8,192-token context, reasoning disabled; fresh application cache per case.
Experiments allowed an empty change list and tried prompt guidance and
examples. This involved 30 calls to the probe across five candidate stages
(34 HTTP requests). All application/schema/prompt candidates were withheld:

| Stage/artifact folder | Cases / HTTP | Finding |
| --- | ---: | --- |
| `layout-noop-candidate` | 1 / 1 | Initial missing-product native-schema case returned a correct no-op explanation. |
| `layout-noop-final` | 8 / 9 | Functional checks passed, but manual review found explanations falsely claiming the requested edit was absent or Korean instructions were unsupported. The folder name does not indicate a released fix. |
| `layout-noop-reason` | 6 / 7 | Language/reason guidance corrected native explanations; JSON mode still repeated the absent-product edit and failed validation. Remaining planned positive controls were not run after that failure. |
| `layout-noop-example` | 9 / 10 | JSON recovered after one retry; manual review found that a request to change nothing copied the example's false missing-product explanation. |
| `layout-noop-neutral` | 6 / 7 | Neutral examples removed that false explanation, but a valid Korean 3,000-won price request also added an unrequested 30% promotion sign. The remaining matrix stopped there. |

The added explanation checks catch the two observed kinds of false reason.
Auditing the 30 stored results found five failures, whereas the older
functional-only checks flagged two. These checks remain limited heuristics;
manual inspection of actions and explanations is still necessary. The final
JSON no-op explanation was also generic, not a complete diagnosis.

The candidate application changes and their experimental tests were removed.
Backend and frontend application/test files are byte-identical to main
`57dcd38a`. This commit only adds diagnostic coverage and records results,
including a separate failed persona schema-order trial in the sampling report.
No automatic clamping, fabricated target substitution or unrelated edit is
introduced to make these cases succeed.

## Verification and evidence

The extended probe replays the previously recorded actual-model
`layout-sequence` result successfully with zero HTTP calls and one cache hit;
this is a compatibility check, not new inference. Probe compilation and diff
checks pass. Application checks are inherited from the unchanged parent:
1,355 focused backend cases, strict Pyright/boot, 70 frontend cases and
TypeScript/lint/build. The published v0.8.2 release is unchanged.

Baseline: `/workspace/scratch/cpu-vlm-probe-2b/missing-layout-baseline/layout-missing-product-json_schema-1793039396528659964/result.json`.
Candidate folders in the table are under `/workspace/scratch/cpu-vlm-probe-2b/`.
Review: `/workspace/scratch/layout-noop-review.json` (preserves original and
reviewed success flags). The known-price regression is
`layout-noop-neutral/layout-price-krw-json_schema-1793040016689616440/result.json`.
Replay: `noop-probe-replay/` under the same root, with log
`/workspace/scratch/noop-probe-replay.log`.

Logs: `/workspace/scratch/missing-layout-baseline.log` and
`/workspace/scratch/layout-noop-{candidate,final-cpu,reason-cpu,example-cpu,neutral-cpu}.log`.
