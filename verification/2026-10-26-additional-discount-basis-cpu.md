# Additional discounts retain the original reference price

On main `91baec1f`, the actual CPU model accepted an English request to take
another 10% off Tea's current $4 selling price while keeping its original
$5 reference. It returned a discount of -10%, which the application always
calculated against $5: the selling price increased to $4.50. The equivalent
Korean request changed 4,000 won to 4,500 instead of 3,600. Both baselines
completed in one request, so successful JSON parsing did not expose the error.

Discount operations now carry `discount_basis`, either `regular` or
`current`. The wire schema requires that choice and the prompts explain the
difference with an example. Stored operations and older responses that omit
it keep the existing `regular` default. The target resolver preserves the
choice; physical and online applications use each offer's current price for
an additional discount and retain its original reference. Sequential cuts
compound on the selling price. Current-price cuts also keep a free offer free.

The A/B editor displays and edits the same choice, previews its price and
preserves it when accepting a model draft or starting a test. Its new labels
and additional-discount summary cover all six supported languages.

## Real CPU observations

Qwen3.5-2B Q4_K_M on llama.cpp b11878, five CPU threads, no GPU,
8,192-token context, reasoning disabled. These calls draft text operations
and apply them through production code to isolated fixtures. They do not
run shoppers or measure sales, and they do not exercise image interpretation.

The first implementation still failed a Korean multi-product case: the
model generated a `promo` operation with text `1` instead of a discount.
That intermediate change was withheld. Placing the changes before the
layout name in the response schema corrected the observed case. The final
production code passed all 14 fresh-cache cases below, each with one HTTP
request and zero application cache hits. Times are observations, not
benchmarks; the server may reuse prompt prefixes.

| Request | Mode | Seconds | Applied result |
| --- | --- | ---: | --- |
| English extra discount | Native schema | 5.49 | $4 → $3.60; original $5 retained |
| Korean extra discount | Native schema | 3.98 | 4,000 → 3,600 won; original 5,000 retained |
| English extra discount | JSON | 11.24 | $3.60 with $5 reference |
| Korean extra discount | JSON | 13.77 | 3,600 with 5,000 reference |
| Set discount against regular price | Native schema | 3.55 | Existing regular-price behavior retained |
| Full discount | Native schema | 4.13 | Zero selling price with original reference |
| Discount and promotion together | Native schema | 6.18 | Both requested operations applied |
| Category price change | Native schema | 3.11 | Target category only |
| Korean fixed price | Native schema | 4.66 | Requested won amount retained |
| Sequential edits | Native schema | 8.11 | Requested sequence applied |
| A/B: extra versus regular-price discount | Native schema | 15.75 | $3.60 versus $4.50; $5 reference in both |
| Same A/B comparison | JSON | 20.15 | Same two requested offers |
| A/B: discount versus sign | Native schema | 11.57 | Existing two-operation comparison retained |
| Same discount/sign comparison | JSON | 20.88 | Same requested offers |

The probes also assert preservation of unrelated products and source stores.
The reusable `local-experiment-probe.py` now includes `extra-discount`.
Earlier 0.8B experiments were not released; their limitations remain recorded
in `2026-10-25-free-offers-cpu.md`. These observations do not establish that
every small model will interpret every discount request correctly.

## Regression checks

The new backend regression file has 17 cases. Against the frozen parent,
eight fail and nine pass; all 17 pass after the change. Coverage includes
USD/KRW/JPY, repeated placements with different prices, free offers, full
discounts, legacy defaults, successive cuts, original-reference preservation,
physical/online parity, real SDK request handling and canonical cache replay
for both layout and experiment drafts in both output modes.

Focused backend verification covers 543 distinct cases. The first broad
pass found two old wire-schema fixtures that omitted the newly required
basis; those were updated, with separate assertions that old runtime/cache
records still load and that unknown wire values fail. The final wire pass
has 42 passing cases. The other 501 passing cases were not needlessly rerun.
Strict Pyright reports zero errors/warnings, server import/boot and probe
compilation pass. Existing LiteLLM asynchronous logging cleanup warnings
remain.

Frontend checks cover 84 cases across five files, including all six language
labels, displayed prices, changes to the selected basis, old saved drafts
and model-draft-to-run serialization. Two initial test queries mishandled
the nonbreaking spaces in Spanish/French currency formatting; using an exact
text normalizer fixed the assertions without changing production formatting.
TypeScript, lint of the four changed TypeScript files and production build
pass. The build retains the existing Babel/chunk-size notices. The published
v0.8.2 release is unchanged; this fix is on main under Unreleased.

## Evidence

Artifacts under `/workspace/scratch/cpu-vlm-probe-2b/`:

- Original failures: `extra-discount-2b-baseline/layout-extra-discount-json_schema-1793033500917605869`
  and `layout-extra-discount-ko-json_schema-1793033509416170349` in the same directory.
- Withheld intermediate Korean failure: `discount-basis-production/layout-extra-discount-ko-json_schema-1793033982811040452`.
- Final layout calls: `discount-basis-final/`, ten `layout-*/result.json` records,
  from timestamp `1793034266073383181` through `1793034343593433927`.
- Final A/B calls: `discount-basis-ab/`, four `ab-*/result.json` records,
  from timestamp `1793034416135078668` through `1793034471552191471`.
- The smaller `discount-basis-diagnostic-*` probe only examined generated
  fields. It is not counted among the 14 application checks.

Logs: `/workspace/scratch/discount-basis-{before,new-tests,focused,wire-final,pyright,boot,ui,tsc,eslint,build}.log`.
