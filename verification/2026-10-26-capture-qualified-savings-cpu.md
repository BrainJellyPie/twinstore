# Qualified savings and cash-back amounts are not selling prices

Actual Qwen3.5-2B Q4_K_M CPU calls on main `ede32886` correctly transcribed
`SAVE UP TO $1.00` and `$1.00 CASH BACK`, with numeric selling price null.
The application nevertheless converted each tag into an exact 100-cent
package price. The savings guard recognized `SAVE` immediately before the
amount and `cashback` as one word, missing these ordinary wording variants.

The guard now accepts explicit savings qualifiers (`up to`, `at least`,
`as much as`) and spaced/hyphenated `cash back`. It checks the observed text
before accepting a numeric guess, including zero amounts. Ordinary prices,
`Cash price`, `Cashback price`, `Save Mart` and an explicitly stated price
`after cashback` remain usable, consistent with existing coupon-price rules.
No prompt, model schema or number of model calls changed.

Both synthetic 448×512 cola/price-tag images were directly inspected. These
are controlled fixtures, not real store photographs or detector coverage.
llama.cpp b11878 used five CPU threads, no GPU and an 8,192-token context.

| Actual call | Observed tag | Application result | Time |
| --- | --- | --- | ---: |
| Before, native JSON Schema | `SAVE UP TO $1.00` | 100 cents exact — failure | 10.86 s |
| Before, native JSON Schema | `$1.00 CASH BACK` | 100 cents exact — failure | 10.92 s |
| After, native JSON Schema | `SAVE UP TO $1.00` | 229 cents estimated — pass | 10.64 s |
| After, native JSON Schema | `$1.00 CASH BACK` | 229 cents estimated — pass | 11.10 s |
| After, plain JSON | `$1.00 CASH BACK` | 189 cents estimated — pass | 13.82 s |
| After, native JSON Schema | `$1.00` | 100 cents exact — pass | 11.15 s |

Every row used one actual HTTP request and zero application cache hits.
Wire formats were `json_schema` or `json_object` as indicated. Native and
JSON observations produced slightly different product names, hence different
catalog estimates; neither estimate is a newly observed selling price.
Server prefix reuse was not disabled; timings are not a speed comparison.
Korean discount/unit words omitted by the model remain a separate limitation.

Artifacts under `/workspace/scratch/cpu-vlm-probe-2b/`:

- `capture-saving-modifiers-before/capture-saving-up-to-json_schema-1793016408343873606`
- `capture-cash-back-before/capture-cash-back-json_schema-1793016442984332955`
- `capture-saving-modifiers-after/capture-saving-up-to-json_schema-1793016556892417865`
- `capture-cash-back-after/capture-cash-back-json_schema-1793016611241012157`
- `capture-cash-back-json-after/capture-cash-back-json-1793016625198329054`
- `capture-saving-modifiers-control/capture-price-json_schema-1793016641842259973`

The initial expanded savings regression suite had 43 failures and 96 passes.
Final focused capture-price tests passed **1,121 tests in 3.47 s**, with 39
existing LiteLLM logging-cleanup warnings. Coverage includes qualified and
zero savings, currencies, Unicode text, model numeric overrides, ordinary
prices, free offers, unit rates and downstream estimated-price handling.
Strict Pyright returned zero errors/warnings; the backend app import,
probe compilation and diff checking passed. Frontend code is unchanged from
the already verified main. Released v0.8.2 changelog content is unchanged.
