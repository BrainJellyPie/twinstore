# Preserve an explicitly printed free price

This follow-up is separate from the v0.8.2 release candidate. Actual
Qwen3.5-2B Q4_K_M CPU inference read `FREE $0.00` correctly and returned
a null numeric price. The converter rejected zero and substituted a
229-cent estimated catalog price for the free product.

The directly inspected fixture is a 448×512 synthetic ACME COLA 500 ml
image, with a yellow `FREE $0.00` strip. It uses known product geometry to
exercise the production VLM label reader and `build_items`, not detection
or real-shop photographic accuracy. llama.cpp b11878 used five CPU threads,
no GPU and an 8,192-token context.

The parser now keeps an exact printed zero when accompanied by compatible
currency or cent units. Existing currency, negative/ambiguous-tag and
savings/reference-price rejection still happens first. A missing price,
unqualified `0`, a model's numeric zero alone or a positive amount rounded
down to zero does not become a free item. `FREE` alone without an amount
is unchanged and remains outside this bounded fix.

| Actual call | Model tag / numeric price | Converted price | Elapsed |
| --- | --- | --- | ---: |
| Before, JSON Schema | `FREE $0.00` / null | 229 cents, estimated — failure | 10.53 s |
| After, JSON Schema | `FREE $0.00` / null | 0 cents, exact — pass | 3.16 s |
| After, JSON | `FREE $0.00` / null | 0 cents, exact — pass | 13.71 s |

Each used one actual HTTP request, a fresh application cache and zero cache
hits. Server prompt-prefix reuse affects elapsed times; these are observations,
not a speed comparison. Brand separation is imperfect in these replies and
is not claimed fixed.

Artifacts under `/workspace/scratch/cpu-vlm-probe-2b/`:

- `capture-free-before/capture-free-price-json_schema-1793010281860542682`
- `capture-free-after/capture-free-price-json_schema-1793010354740788625`
- `capture-free-json/capture-free-price-json-1793010402592737419`

New regressions on the old converter first produced 26 failures and 30
passes. Final free-price, savings/reference, numeric boundary, text-format,
safety and currency checks passed all 1,002 cases in 3.42 s, with 39 existing
LiteLLM logging cleanup warnings. Cases include USD/EUR/KRW/JPY, full-width
text, wrong currency, negative zero, savings/reference zeros, percentages,
conflicting amounts, absent tags and sub-minor-unit positive prices. Placement
checks cover both a new product and replacement of an existing paid offer,
including preservation of the input store and unrelated racks.
Strict backend Pyright reported zero errors/warnings, the app import smoke
passed, and probe compilation/diff checks passed. Frontend code is unchanged.
