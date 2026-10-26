# Preserve explicit container counts in price and catalog matching

Actual Qwen3.5-2B Q4_K_M CPU inference reproduced two conversion errors on
main `8d02bc65`, after the existing `6 PACK` protections were integrated:

- Capture read size `6 BOTTLES` and tag `$1.00 / BOTTLE` correctly, then
  stored 100 cents as the exact price of the whole pack.
- Package reading transcribed `LEAFY GREEN TEA 500 ml 6 BOTTLES` correctly,
  then offered and linked the single-bottle catalog entry
  `Leafy Green Tea 500 ml`. The separate size field held only `500 ml`.

Recognized bottle/can/jar quantities now participate in both guards, including
the supported Korean/Japanese counters and full-width text. Counts above one
prevent a container rate from becoming an exact pack price, and must remain
present in supported catalog candidates. A count of one does not require a
multipack name. Existing numeric overrides, per-pack selling prices, single
container prices, word boundaries and source-store preservation remain tested.
Prompts, response schemas and inference parameters are unchanged. Filtering
all unsupported candidates also avoids the unnecessary second matching call.

The two synthetic fixtures were inspected directly: a 448×512 cola label
with a price tag, and a 600×800 tea label. Each has a bottle-shaped graphic
with `6 BOTTLES` printed on it; neither depicts six physical bottles or is a
retail photograph. This isolates label observation and conversion, not object
detection. llama.cpp b11878 used five CPU threads, no GPU and an 8,192-token
context. Every row below used actual HTTP inference with zero application
cache hits. Server prompt-prefix reuse was possible; timings are not a speed
comparison.

| Case | Wire mode | Result | Calls | Time |
| --- | --- | --- | ---: | ---: |
| Capture before | `json_schema` | 100 cents exact: failure | 1 | 10.59 s |
| Capture after | `json_schema` | 189 cents estimated: pass | 1 | 3.99 s |
| Capture after | `json_object` | 189 cents estimated: pass | 1 | 13.97 s |
| Package, single-only catalog, before | `json_schema` | Wrong single-bottle link | 2 | 18.11 s |
| Package, single-only catalog, after | `json_schema` | No unsupported link | 1 | 3.41 s |
| Package, single + correct multipack, after | `json_schema` | Correct six-bottle link | 2 | 5.71 s |
| Package, single-only catalog, after | `json_object` | No unsupported link | 1 | 18.00 s |

The 189-cent fallback is a catalog estimate, not an observed selling price.
This remains bounded evidence matching: equivalent but differently worded
count descriptions may need review, and counts omitted by the model cannot
be recovered by these guards. No general OCR accuracy improvement is claimed.

Artifacts under `/workspace/scratch/cpu-vlm-probe-2b/`:

- `capture-container-count-before/capture-container-count-price-json_schema-1793020215339105880`
- `capture-container-count-after/capture-container-count-price-json_schema-1793020637953043890`
- `capture-container-count-json-after/capture-container-count-price-json-1793020805638617743`
- `pack-container-count-before/pack-multipack-count-unlisted-json_schema-1793020652423699401`
- `pack-container-count-after/pack-multipack-container-count-unlisted-json_schema-1793020773043111734`
- `pack-container-count-control/pack-multipack-container-count-json_schema-1793020822632993550`
- `pack-container-count-json-after/pack-multipack-container-count-unlisted-json-1793020831233401210`

The before runs used scratch copies of the probe with only fixture text and
case selection changed; production code was unchanged. The committed probe
now includes the explicit-container capture case and both package catalogs.
Before the fixes, focused price regressions produced 24 failures / 79 passes,
and package label regressions produced 10 failures / 44 passes.

Final focused validation passed **1,430 tests across 17 files in 10.11 s**,
with 54 existing LiteLLM logging-cleanup warnings. Strict backend Pyright
returned zero errors/warnings, and the app import passed. Probe compilation
and diff checks passed. Frontend code is unchanged, and the released
v0.8.2 changelog section remains byte-identical to the tag.
