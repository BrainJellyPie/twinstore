# Reference prices must not become exact current selling prices

This follow-up is based on v0.8.2 candidate `b0e439cd` and is deliberately
outside that release. Actual Qwen3.5-2B Q4_K_M CPU inference reproduced a
conversion bug: the model correctly read `WAS $1.00` and left numeric price
null, but `build_items` stored 100 cents as an exact current selling price.

The fixture is a directly inspected 448×512 synthetic ACME COLA 500 ml
image with a yellow `WAS $1.00` strip, not a real shop photograph. Known
geometry isolates the production VLM label reader and item conversion;
this does not evaluate product detection. llama.cpp b11878 used five CPU
threads, no GPU and an 8,192-token context.

The price parser now recognizes the bounded reference-price prefixes
`WAS`, `MSRP` and `RRP`, as well as an optional colon on recognized savings
or reference tags. It preserves the product and tag while using the existing
catalog fallback with `price_estimated=true`. Ordinary selling-price wording,
including `NOW`, `Our price`, `with coupon` and `할인가`, remains accepted.
`Wasabi` verifies that a product word is not mistaken for the prefix `WAS`.

| Actual JSON Schema call | Observed tag / numeric price | Converted item | Time |
| --- | --- | --- | ---: |
| Before | `WAS $1.00` / null | 100 cents, exact — failure | 9.97 s |
| After | `WAS $1.00` / null | 229 cents, estimated — pass | 3.16 s |

Each observation made one real HTTP request with a fresh application cache
and zero cache hits. Server prompt-prefix reuse can affect elapsed time;
these timings are not a speed benchmark. The model included brand and size
in its name field, so this is not a claim of perfect product identification.

Artifacts under `/workspace/scratch/cpu-vlm-probe-2b/`:

- `capture-reference-before/capture-was-price-json_schema-1793008241862783852`
- `capture-reference-after/capture-was-price-json_schema-1793008321977852739`

The new regression cases against the old converter produced 18 failures
and 74 passes. Final savings, price-text, numeric-safety and currency tests
passed all 270 cases in 2.86 s, with 39 existing LiteLLM logging cleanup
warnings. Backend strict Pyright reported zero errors/warnings and the app
import smoke passed. Frontend code is unchanged.

A separate explicit selling/savings/unknown model-classification prototype
was withheld: actual CPU runs misclassified Korean sale prices and prices
available with a coupon. Neither that field nor its prompt changes are in
this patch. The previously documented Korean discount-word omission remains
unresolved; this bounded parser cannot recover missing visual observations.
