# Package net size versus serving references

On main `4a15b81f`, a real CPU VLM correctly transcribed `NET 500 ml PER
100 ml` and reported a net size of `500 ml`, but linked the image to
`Leafy Green Tea 100 ml` when that was the only catalog candidate. All its
words were present in the label, so the evidence filter let it through.
When both sizes were available, the baseline chose the correct 500 ml
product. The synthetic image was visually inspected for readable,
unclipped text; these are real reading/matching calls, not detection tests.

Candidates with an explicit quantity contradicting the observed net size
in the same unit are now excluded before matching. The net-size field must
already occur in the transcribed label. Decimal spellings are compared
numerically. Names without sizes, compatible multipacks and alternative
units retain their existing matching behavior. The matching instruction
also distinguishes nutrition/serving references from net size. If no
supported candidate remains, no matching request is necessary.

This guard does not establish the truth of a model's observation or convert
between different units. Missing, unsupported or wrongly read net metadata
retains the existing limitations; no size is fabricated.

## Actual CPU checks

Qwen3.5-2B Q4_K_M with mmproj F16, llama.cpp b11878, five CPU threads,
no GPU, 8,192-token context, disabled reasoning and temperature zero.
Each row has a fresh application cache and zero application cache hits.
The llama server may reuse prompt prefixes; times are observations, not
cold-start benchmarks.

| Stage / catalog | Mode | Seconds | HTTP calls | Outcome |
| --- | --- | ---: | ---: | --- |
| Baseline: only 100 ml | Native schema | 17.94 | 2 | Incorrect 100 ml link |
| Baseline: both sizes | Native schema | 4.56 | 2 | Correct 500 ml link |
| Repaired: only 100 ml | Native schema | 3.33 | 1 | No link |
| Repaired: both sizes | Native schema | 5.54 | 2 | Correct 500 ml link |
| Repaired: only 100 ml | JSON | 18.38 | 1 | No link |
| Repaired: both sizes | JSON | 7.22 | 2 | Correct 500 ml link |
| Six-pack control | Native schema | 19.66 | 2 | Correct six-pack link |
| Brand-after-size control | Native schema | 15.75 | 2 | Correct full-name link |

All six final semantic checks pass. Native observations omit the separate
brand field in several cases while retaining it in printed text and the
name; the evidence-based link remains correct.

## Regression checks and integration

The first 20 new regression cases fail 10 and pass 10 on the parent.
The final file has 30 passing cases, adding decimal-equivalence controls
and both wire modes through the HTTP adapter, candidate enums, malicious
matching replies, cached observations and a changed catalog. Broader
verification passes 236 tests across all 10 package engine/API files in
8.77 seconds, with 18 existing LiteLLM logging-cleanup warnings. Strict
Pyright reports zero errors/warnings; server boot, compilation and diff
checks pass. No full suite is rerun. Frontend code is unchanged and inherits
410's 117 UI tests, TypeScript/lint and production build.

The external branch's `b16cfc2f` only merges already integrated main
`ec878593` into `38f0bb1c`. Preserve its ancestry, resolving the changelog's
paragraph-order conflict with the existing complete main entries. There
is no new external application change. Released notes and v0.8.2 remain
unchanged.

Artifacts: `/workspace/scratch/cpu-vlm-probe-2b/pack-serving-baseline/`
and `pack-serving-final/`; their results include request/reply bodies,
images and cache counts. Logs:
`/workspace/scratch/pack-serving-{baseline,before,core-tests,final-cpu,tests,pyright,boot}.log`.
Focused file list: `/workspace/scratch/pack-serving-test-files.json`.
