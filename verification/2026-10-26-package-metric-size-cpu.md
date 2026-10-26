# Keep metric serving references out of package identity

On main `a43dab75`, the actual CPU VLM reads a package's net size as
**0.5 L**, but the matcher links it to **Leafy Green Tea 100 ml**. That
smaller amount is printed only as `PER 100 ml`. The existing guard compares
amounts only when their unit strings agree, so it misses this contradiction
between litres and millilitres.

The guard now also compares unambiguous metric quantities on a common
basis: `ml`, `cl`, `dl`, `l` for volume, and `mg`, `g`, `kg` for mass.
Decimal exponents are shifted exactly, avoiding context-dependent rounding
even for long permitted values. Ambiguous `1,000` / `1.000` separators do
not establish new cross-unit contradictions. Existing same-unit checks
remain. No conversion between mass and volume, imperial units or arbitrary
unit spellings is inferred.

This only rejects contradictory candidates. Catalog names still require
their original printed-word evidence; the conversion does not invent an
unprinted alternate name. Equivalent quantities are retained when both
representations are printed. Missing or incorrectly observed net sizes
remain limitations of the image-reading stage, as before.

## Actual CPU observations

Qwen3.5-2B Q4_K_M, mmproj F16, llama.cpp b11878, five CPU threads,
no GPU, 8,192-token context, reasoning disabled and temperature 0.
The synthetic package with `NET 0.5 L` and `PER 100 ml` was visually
inspected. This is a label-recognition fixture, not a real package photo
or an object-detection benchmark. Every run has a fresh application cache
and zero cache hits. Timing varies with server prefix reuse.

The baseline takes 18.40 seconds and two actual HTTP calls, incorrectly
linking the only listed 100 ml product despite observing `size="0.5 L"`.
All six final cases pass:

| Catalog / printed evidence | Mode | HTTP calls | Seconds | Link |
| --- | --- | ---: | ---: | --- |
| Only the 100 ml reference product | Native schema | 1 | 3.41 | Empty |
| 100 ml reference plus correct 0.5 L product | Native schema | 2 | 4.66 | 0.5 L product |
| Both 0.5 L and 500 ml printed; 500 ml catalog entry | Native schema | 2 | 15.90 | 500 ml product |
| Only the 100 ml reference product | JSON | 1 | 17.85 | Empty |
| 100 ml reference plus correct 0.5 L product | JSON | 2 | 6.41 | 0.5 L product |
| Both 0.5 L and 500 ml printed; 500 ml catalog entry | JSON | 2 | 18.47 | 500 ml product |

When every candidate contradicts the observed size, no matching request
is needed. The native observations leave `brand` empty despite including
Leafy in the recognized name; these tests do not establish complete OCR
or metadata quality.

## Regression evidence

The first expanded net-size file has **32 failures and 36 passes** on the
parent. The final file has 76 cases, including both wire modes, cached
observations, changed catalogs, disallowed matcher replies, decimal comma,
full-width text, equivalent units and ambiguous separators. A precision
prototype can round distinct long values together; the final exponent
conversion distinguishes them. Two initial precision fixtures exceeded
the existing size-field length limit and were corrected to valid
30-character size inputs before final verification.

The focused engine/API suite passes **282 tests across 10 files in 8.53
seconds**, with 30 existing LiteLLM asynchronous logging-cleanup warnings.
Strict Pyright has zero errors/warnings. Boot, probe compilation, diff
and released-note preservation checks pass. Frontend code is unchanged,
inheriting 416's 55 UI tests and type/build/lint checks. No full release
suite is repeated; released v0.8.2 artifacts and notes are unchanged.

Artifacts under `/workspace/scratch/cpu-vlm-probe-2b/`:
- Baseline: `pack-cross-unit-baseline/pack-cross-unit-reference-unlisted-json_schema-1793054404245825841`.
- Native no-match: `pack-cross-unit-final/pack-cross-unit-reference-unlisted-json_schema-1793054980362386818`.
- Native correct match: `pack-cross-unit-final/pack-cross-unit-reference-json_schema-1793054986678461050`.
- Native equivalent: `pack-cross-unit-final/pack-metric-equivalent-json_schema-1793054994317520767`.
- JSON no-match: `pack-cross-unit-final/pack-cross-unit-reference-unlisted-json-1793055013245364133`.
- JSON correct match: `pack-cross-unit-final/pack-cross-unit-reference-json-1793055033970957161`.
- JSON equivalent: `pack-cross-unit-final/pack-metric-equivalent-json-1793055043216271843`.

Logs: `/workspace/scratch/pack-cross-unit-{baseline,before,core,tests-verified,pyright-final,boot,final-cpu}.log`.
Precision evidence: `/workspace/scratch/pack-cross-unit-precision-evidence.json`.
Focused list: `/workspace/scratch/pack-cross-unit-test-files.json`.
Final result summary: `/workspace/scratch/pack-cross-unit-final-summary.json`.
