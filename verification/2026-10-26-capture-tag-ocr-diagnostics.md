# Korean price-tag transcription diagnostics — withheld

The real Qwen3.5-2B Q4_K_M CPU capture probe still drops `리터당` from
`리터당 1,000원`, which makes the observed amount look like an exact package
price. The existing parser cannot recover words missing from its observation.
These experiments investigate that limitation; none changes product code.

The source is the directly inspected synthetic 448×512 cola-and-price-tag
fixture, not a store photograph. llama.cpp b11878 runs with no GPU, five CPU
threads and an 8,192-token context. All rows made one actual HTTP request with
native `json_schema`. Harness runs used fresh application caches with zero
hits; direct HTTP diagnostics have no application cache layer. Server prompt
prefix reuse was not disabled, so these times are not a speed comparison.

| Diagnostic | Observed text | Result | Time |
| --- | --- | --- | ---: |
| Price-tag crop only; single literal-text field | `리터당 1,000원` | Correct isolated transcription | 3.22 s |
| Original full image; price_text first plus explicit first-transcription instruction | `1,000원` | Unit word still missing; exact package price still wrong | 11.43 s |
| Same pixels rearranged with tag above product; corresponding layout prompt | `1,000원` | Unit word still missing; exact package price still wrong | 10.72 s |
| Original full image; single literal-text field, asking for bottom yellow tag | `ACME COLA 500 ml 리터당 1,000원` | Unit word retained, but product text incorrectly included | 8.07 s |

The first result changed both image crop and response task; it does not prove
cropping alone fixes the problem. The last result demonstrates another
boundary: a simplified transcription task retains the unit word but fails
to isolate the requested tag. No extra production model calls, schema change
or image transformation were shipped from these diagnostics. Korean unit-rate
and discount-word omissions remain known model observation limitations.

Artifacts under `/workspace/scratch/cpu-vlm-probe-2b/`:

- `price-tag-crop-diagnostic-1793014528289063052`
- `capture-tag-first-explicit-diagnostic/capture-unit-price-krw-json_schema-1793014719610581247`
- `capture-tag-top-diagnostic/capture-unit-price-krw-json_schema-1793015250501460268`
- `price-tag-full-image-diagnostic-1793015474606467780`

Each directory retains the image, actual request and response/result. The
prior schema-order-only failure is documented in
`2026-10-26-capture-unit-rates-cpu.md` and is not counted again here.
