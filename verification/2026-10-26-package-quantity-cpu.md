# Package quantities must not become selling prices

On main `d82337a5`, actual CPU recognition returned the exact tags `500 ml`
and `6 PACK`, with null model prices. Conversion nevertheless marked them
as exact prices of 500 and 600 cents. The amount/unit heuristics were treating
a volume or pack count as money.

Conversion now refuses bare mass/volume quantities and recognized pack/count
labels when they supply no explicit cash unit. The printed tag is preserved,
the usual fallback is marked estimated and a matched product's existing
price survives placement. Cash labels such as `$6 PACK`, recognized currency
codes and cents still establish prices. Unqualified numeric tags retain
their existing interpretation. Model prompts/schemas are unchanged.

## Actual CPU observations

Qwen3.5-2B Q4_K_M on llama.cpp b11878, five CPU threads, no GPU,
8,192-token context, reasoning disabled. Each run used two HTTP requests and
zero application cache hits. Synthetic images were inspected visually;
known geometry isolates product/tag recognition and production conversion,
not full-shelf detection. Times are observations, not comparative benchmarks.

| Tag | Mode | Seconds | Result |
| --- | --- | ---: | --- |
| 500 ml baseline | Native schema | 13.26 | Incorrect exact 500 cents |
| 6 PACK baseline | Native schema | 12.97 | Incorrect exact 600 cents |
| 500 ml repaired | Native schema | 13.17 | Estimated 189 cents |
| 500 ml repaired | JSON | 18.78 | Estimated 229 cents |
| 6 PACK repaired | Native schema | 12.93 | Estimated 229 cents |
| 6 PACK repaired | JSON | 14.13 | Estimated 229 cents |
| $6 PACK control | Native schema | 14.30 | Exact 600 cents retained |

Fallbacks vary with the model's product/category interpretation; they do not
recover an actual price from a quantity. The three tags are retained as
reusable capture probe cases.

## Regression checks

The expanded measure/quantity file fails 54 cases and passes 83 against the
parent. Its 137 cases pass after repair. Final broader verification passes
1,468 cases across nine capture files in 4.12 seconds. Coverage includes
fractional sizes, fullwidth units, mass/volume abbreviations, Korean units,
pack prefixes/suffixes, one-item and zero quantities, currency-code/symbol
controls, numeric model guesses and preservation of an existing 375-cent
price, unrelated shelves and source store. Sixteen existing LiteLLM cleanup
warnings remain. Strict Pyright/boot, probe compilation and diff checks pass.
Frontend is unchanged; the parent's 167 UI checks and TypeScript/lint/build
remain applicable and were not rerun. v0.8.2 assets/tag remain unchanged.

Evidence under `/workspace/scratch/cpu-vlm-probe-2b/`:

- `quantity-baseline/capture-volume-only-json_schema-1793040974340220927/result.json`.
- `quantity-baseline/capture-count-only-json_schema-1793040990668782625/result.json`.
- Five repaired records in `quantity-final/`, timestamps
  `1793041173663903989` through `1793041244793004128`.

Logs: `/workspace/scratch/quantity-{baseline-cpu,final-cpu,before,unit-tests,tests,pyright,boot}.log`.
