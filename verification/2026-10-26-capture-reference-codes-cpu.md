# Prevent reference numbers from becoming shelf selling prices

Actual CPU reads on main `d2e7d66b` faithfully transcribed `SKU 1234`,
`LOT 1234` and `EXP 2026`, but the price converter treated the numbers as
exact selling prices of 12.34, 12.34 and 20.26 USD. All three semantic
checks failed despite correct visual transcription and valid structured
output. The synthetic fixture images were visually inspected for readable,
unclipped labels; these are isolated recognition/conversion tests, not
photographic shelf detection benchmarks.

The converter now recognizes marked product/lot/serial identifiers and
expiry/manufacture dates without monetary units. Such labels retain their
printed text and estimated fallback price; applying a capture to an existing
matched product preserves its saved selling price. A numeric model guess
cannot override that printed nonmonetary context. Explicit currency prices,
ordinary unmarked numeric price tags and similarly named products remain
usable. The check covers recognized prefixes, not every possible identifier
or date spelling. It does not infer a new price from a reference number.

## Actual CPU verification

Qwen3.5-2B Q4_K_M, llama.cpp b11878, five CPU threads, no GPU,
8,192-token context, disabled reasoning and temperature zero. Each row uses
two actual HTTP requests (product reading plus separate tag transcription),
a fresh application cache and zero application cache hits.

| Stage / tag | Mode | Seconds | Stored price outcome |
| --- | --- | ---: | --- |
| Baseline SKU 1234 | Native schema | 14.14 | Incorrect exact 12.34 USD |
| Baseline LOT 1234 | Native schema | 13.52 | Incorrect exact 12.34 USD |
| Baseline EXP 2026 | Native schema | 13.39 | Incorrect exact 20.26 USD |
| Repaired SKU 1234 | Native schema | 13.49 | Estimated 1.89 USD |
| Repaired LOT 1234 | Native schema | 13.91 | Estimated 2.29 USD |
| Repaired EXP 2026 | Native schema | 14.02 | Estimated 1.89 USD |
| Repaired SKU 1234 | JSON | 17.57 | Estimated 2.29 USD |
| Repaired EXP 2026 | JSON | 13.60 | Estimated 1.89 USD |
| Exact $1.00 control | Native schema | 13.90 | Exact 1.00 USD retained |

All six final cases pass. Estimated values are catalog fallbacks, not claims
about a photographed selling price. Product names and printed tag text remain
available for review. Times are observations, not benchmarks.

## Regression checks

The new reference-code tests fail 93 cases and pass 15 on the parent; all
108 pass after the repair. They cover English/Korean/Japanese labels,
full-width spelling, model price guesses, currency-bearing controls and
preservation of known/new products during capture placement. Broader checks
pass 1,744 cases across 12 affected/adjacent capture files in 5.03 seconds,
including cents/currency, free prices, savings, deposits, price limits,
unit rates, multipacks and separate tag reading. Thirty-nine existing
LiteLLM asynchronous-logging cleanup warnings remain.

Strict Pyright, server boot, probe compilation and diff checks pass.
Frontend code is unchanged and inherits 44 focused product-library cases
plus TypeScript/lint/build. Released changelog text and v0.8.2 tag/assets
remain unchanged.

Evidence under `/workspace/scratch/cpu-vlm-probe-2b/`:
- `capture-code-baseline/` contains the three failed real-model results.
- `capture-code-final/` contains the six passing real-model results, beginning
  with `capture-sku-code-json_schema-1793046829650811172`.

Logs: `/workspace/scratch/capture-code-{baseline,before,core-tests,final-cpu,tests,pyright,boot}.log`.
Focused file list: `/workspace/scratch/capture-code-test-files.json`.
