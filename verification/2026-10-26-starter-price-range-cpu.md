# Currency-readable starter prices and explicit lower bounds

On main `9cf30123`, an actual CPU bookstore run requested books priced
15–20 USD each, inclusive, and at most one product per category. The model
retained the correct Books/Stationery shelves and valid product IDs, but
selected the 9.99 USD Pocket Poetry Collection. The strengthened probe
correctly failed this result (23.63 seconds, two HTTP requests).

The product-selection input exposed stored integers without price units,
for example `999` for a 9.99 USD shelf price. Product prompts now receive
printed currency amounts through the existing display_price formatter,
such as `$9.99`, `27,000원` and `¥2,850`. Primary and recovery prompts
explicitly require both bounds: a cheaper product below a requested
minimum is not eligible. Stored catalog prices and SKU identities are
untouched; the model still selects existing product codes only.

## Investigation

Formatted prices and a general range instruction passed five initial
full-flow cases (USD native/JSON, KRW, JPY and a no-price-range control).
An isolated small-product recovery task still chose 2,250 JPY against a
2,800–3,100 JPY range. USD recovery chose a valid 19.99 USD product.

Moving requirements after the catalog did not fix the JPY case. Neither
did removing the example product code, using plain major-unit strings, or
a raw-integer JPY input trial. Those ordering/example changes are not in
the final application diff. The raw-integer trial used the candidate
prompt; it is not claimed as an exact parent-version baseline. Explicitly
stating that prices below the minimum are ineligible corrected this
observed recovery failure: native USD chooses 1,999 cents and JPY chooses
3,000 yen. Final full-flow checks were repeated after that prompt change.

These runs use Qwen3.5-2B Q4_K_M, llama.cpp b11878, five CPU threads,
no GPU, 8,192-token context, reasoning disabled and temperature zero.
Every fresh run has zero application cache hits. The model is vision-capable,
but this assortment task is text-based. Times are observations, not benchmarks.

| Final full flow | Mode | Seconds | Selected book price |
| --- | --- | ---: | --- |
| 15–20 USD | Native schema | 23.56 | 19.99 USD |
| 15–20 USD | JSON | 30.25 | 19.99 USD |
| 25,000–28,000 KRW | Native schema | 23.54 | 27,000 KRW |
| 2,800–3,100 JPY | Native schema | 10.09 | 2,850 JPY |
| No price range, two products/category | JSON | 33.56 | Four valid selected/placed SKUs |

Every full-flow row uses two HTTP requests. The fixtures also check
shelf purposes, exclusions, per-category limits, source immutability,
selected/placed identities and exact stored catalog prices. The reusable
probe retains all three currency-range cases.

Final isolated small-product checks pass in native schema and JSON modes:
USD selects 19.99 USD in 3.15 and 4.45 seconds; JPY selects 3,000 yen in
2.20 and 2.09 seconds. Each uses one actual model request and zero cache
hits. Together with the five full-flow cases, all nine final checks pass.

The small-task runs call the real recovery helper directly. They do not
claim that an earlier primary failure or subsequent placement occurred.
These fixtures have suitable catalog products. No claim is made for
infeasible ranges or universal interpretation of natural-language rules;
production's hard validators still enforce IDs and counts, not arbitrary
free-text price conditions.

## Evidence and checks

Artifacts under `/workspace/scratch/cpu-vlm-probe-2b/`:

- Baseline `starter-price-baseline/book-price-range-json_schema-1793043676415732106`.
- Initial formatted-price full-flow trials in `starter-price-candidate/`
  and `starter-price-controls/`.
- Recovery trials in `starter-small-price/`, `starter-small-price-major/`
  and `starter-small-price-raw/`. Final native records are
  `USD-1793044435223665954` and `JPY-1793044438374774633` under the first folder.
- Final full-flow records in `starter-price-final/`, beginning with
  `book-price-range-json_schema-1793044525725485302`.
- JSON recovery records in `starter-small-price-json/`.
- Recovery runners `/workspace/scratch/probe-starter-small-price*.py` preserve
  their input price representation, requested bounds and selected prices.

Focused regression checks pass 1,213 backend cases in 42.42 seconds,
covering starter schemas, catalog identities/prices, exclusions, limits,
adaptive recovery, cache reuse and the affected API paths. Six existing
LiteLLM asynchronous logging cleanup warnings remain. Strict Pyright reports
zero errors/warnings; server boot, probe compilation and diff checks pass.
No full suite is rerun.

Frontend code is unchanged and inherits 138 focused UI cases and
TypeScript/lint/build. Released changelog text and v0.8.2 tag/assets remain
unchanged. Logs: `/workspace/scratch/starter-price-{baseline,candidate,controls,final-cpu,tests,pyright,boot}.log`
and `/workspace/scratch/starter-small-price*.log`.
