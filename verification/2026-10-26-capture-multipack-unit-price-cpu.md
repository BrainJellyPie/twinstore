# Do not price a whole multipack at a printed bottle rate

Actual Qwen3.5-2B Q4_K_M CPU inference on main `6f50fa4f` returned
`ACME COLA 6 PACK`, size `6 PACK`, tag `$1.00 / BOTTLE` and numeric price 1.
The capture converter stored 100 cents as the exact price of the whole pack.
Both the quantity and the named-container rate were available in the model's
observation, so this was a conversion error rather than missing OCR evidence.

The converter now recognizes explicit pack counts and multiplied volume/weight
quantities in the observed size or name. For counts above one, a recognized
bottle/can/jar rate is not an exact package price, even if the model supplied
a positive numeric guess. It preserves the product/tag and estimated fallback;
applying it over a known pack preserves the existing price. No multiplication
of an uncertain model-read count into a new selling price is inferred.
Ordinary selling prices, per-pack prices and single-container rates remain
usable. This is bounded recognition of the documented forms, not a universal
package-unit parser. No model prompt, schema or call count changed.

The 448×512 synthetic images were directly inspected. A bottle-shaped graphic
has a clearly printed `6 PACK` label: it is not a photograph or a rendering
of six physical bottles. The single-bottle control instead prints `500 ml`.
The experiment isolates label reading and conversion, not shelf detection.
llama.cpp b11878 used five CPU threads, no GPU and an 8,192-token context.

| Actual call | Printed package / returned tag | Application result | Time |
| --- | --- | --- | ---: |
| Before, native JSON Schema | 6 PACK / `$1.00 / BOTTLE` | 100 cents exact — failure | 11.41 s |
| After, native JSON Schema | 6 PACK / `$1.00 / BOTTLE` | 189 cents estimated — pass | 3.41 s |
| After, plain JSON | 6 PACK / `$1.00 / BOTTLE` | 189 cents estimated — pass | 14.09 s |
| After, native JSON Schema | 6 PACK / `$6.00 / PACK` | 600 cents exact — pass | 10.62 s |
| After, native JSON Schema | 500 ml / `$1.00 / BOTTLE` | 100 cents exact — pass | 11.64 s |

Every row made one actual HTTP request with zero application cache hits.
Wire modes were `json_schema` and `json_object` as stated. Server prompt-prefix
reuse was possible; the timing difference is not a speed result. The estimated
189 cents is a catalog fallback, not an observed price. Counts or unit words
omitted by the model remain outside this guard's evidence.

Artifacts under `/workspace/scratch/cpu-vlm-probe-2b/`:

- `capture-pack-unit-before/capture-pack-unit-price-json_schema-1793019051404156015`
- `capture-pack-unit-after/capture-pack-unit-price-json_schema-1793019370701758094`
- `capture-pack-unit-json-after/capture-pack-unit-price-json-1793019486134868897`
- `capture-pack-price-control/capture-pack-price-json_schema-1793019472715541081`
- `capture-single-bottle-control/capture-bottle-price-json_schema-1793019503199267064`

The new regression suite first failed 45 cases and passed 14. Final focused
capture-price checks passed **1,180 tests in 5.71 s** with 39 existing LiteLLM
logging-cleanup warnings. They cover count spelling, Unicode, nested/reversed
multiplication, currencies, numeric overrides, zero rates, false-count controls,
pack/single prices, and preservation of an existing pack offer without mutating
the source store. Strict Pyright returned zero errors/warnings and the app
import passed. Probe compilation and diff checks passed. Frontend code and
released v0.8.2 changelog content are unchanged.
