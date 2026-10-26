# Loyalty counts are not cash prices

On main `5ae188fb`, the actual CPU model read `100 POINTS` and `100포인트`
correctly and returned null numeric prices. The converter nevertheless
treated them as exact selling prices: 100 cents in the USD fixture and
100 won in the KRW fixture. A point count establishes neither amount nor
an exchange rate in either currency.

The non-selling-label guard now recognizes point/points, pt/pts, Korean,
Japanese and simplified/traditional Chinese point labels. The tag remains
visible, its usual fallback is marked estimated, and a matched product's
existing selling price is preserved. Explicit conditional cash-price labels
remain usable. Prompts, model schemas and sampling are unchanged.

## Actual CPU observations

Qwen3.5-2B Q4_K_M, llama.cpp b11878, five CPU threads, no GPU,
8,192-token context, reasoning disabled. Each case made two HTTP requests
with zero application cache hits, reading the product and tag separately.
Synthetic images were visually inspected. Known geometry isolates production
recognition and `build_items`; this is not a detector benchmark or a real
shelf accuracy claim. Durations are observations, not comparative timings.

| Case | Mode | Seconds | Converted result |
| --- | --- | ---: | --- |
| 100 POINTS baseline | Native schema | 14.17 | Incorrect exact 100 cents |
| 100포인트 baseline | Native schema | 13.14 | Incorrect exact 100 won |
| 100 POINTS repaired | Native schema | 13.45 | Estimated 229 cents |
| 100 POINTS repaired | JSON | 17.49 | Estimated 229 cents |
| 100포인트 repaired | Native schema | 13.35 | Estimated 3,100 won |
| 100포인트 repaired | JSON | 13.03 | Estimated 2,600 won |
| $1.00 WITH POINTS control | Native schema | 13.96 | Exact 100 cents retained |

The differing Korean estimates reflect product/category interpretation; they
are not claims about the photographed product's real price. Japanese and
Chinese point labels were exercised as unit cases, not extra VLM calls.

## Regression checks

The expanded savings file fails 40 cases and passes 236 against the parent.
After repair, 1,403 focused cases across nine capture files pass in 3.80
seconds, including prefixes/suffixes, abbreviations, fullwidth text, zero,
numeric model guesses, conditional cash-price controls, unknown/known SKUs,
unrelated shelves and source immutability. Sixteen existing LiteLLM cleanup
warnings remain. Strict Pyright reports zero errors/warnings; boot/import,
probe compilation and diff checks pass. Frontend is unchanged, so the
parent's 167 UI cases and TypeScript/lint/build checks are inherited.

Evidence under `/workspace/scratch/cpu-vlm-probe-2b/`:

- `points-baseline/capture-points-json_schema-1793040486313843813/result.json`.
- `points-baseline/capture-points-krw-json_schema-1793040503457473950/result.json`.
- Five passing records in `points-final/`, timestamps
  `1793040655725192275` through `1793040724770779677`.

Logs: `/workspace/scratch/points-{baseline-cpu,final-cpu,before,tests,pyright,boot}.log`.
This fix is Unreleased on main; v0.8.2 tag and assets are unchanged.
