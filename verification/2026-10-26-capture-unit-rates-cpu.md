# Do not save a per-measure rate as an exact package price

Actual Qwen3.5-2B Q4_K_M CPU inference on main `ef149060` correctly read
`$1.00 / L` from a 500 ml cola fixture and returned numeric price 1.0. The
converter then stored 100 cents as the exact price of the package. That rate
does not establish the package selling price.

The parser now rejects recognized weight/volume rate wording before accepting
the numeric guess: slash variants, `per litre`, `per kg`, recognized measure
units and explicit Korean/Japanese per-unit suffixes. The product and tag are
retained, the fallback is marked estimated, and placement preserves an
existing store price. `each`, `per item`, `/bottle` and ordinary selling tags
remain usable. The prompt asks the model to retain rate wording and leave the
numeric selling price unknown. No package-price conversion is inferred from
model-estimated size.

The directly inspected 448×512 synthetic fixtures show ACME COLA 500 ml and
a yellow price strip; these are not real store photographs. Known geometry
isolates the production VLM label reader and conversion, not detection.
llama.cpp b11878 used five CPU threads, no GPU and an 8,192-token context.

| Actual call | Returned tag / numeric price | Outcome | Time |
| --- | --- | --- | ---: |
| Before, `$1.00 / L`, JSON Schema | `$1.00 / L` / 1.0 | 100 cents exact — failure | 11.21 s |
| After, `$1.00 / L`, JSON Schema | `$1.00 / L` / null | Estimated fallback — pass | 10.81 s |
| After, `$1.00 / L`, JSON | `$1.00 / L` / 1.0 | Estimated fallback — pass | 14.90 s |
| After, ordinary `$1.00`, JSON Schema | `$1.00` / 1.0 | 100 cents exact — pass | 11.26 s |
| Before, `리터당 1,000원`, JSON Schema | `1,000원` / 1000 | Unit word omitted — failure | 10.95 s |
| After, `리터당 1,000원`, JSON Schema | `1,000원` / 1000 | **Still fails** | 11.40 s |

Every row used one actual HTTP request and zero application cache hits.
Native runs used `json_schema` on the wire; the plain-JSON run used
`json_object`. Prefix reuse may affect time; this is not a speed comparison.
Estimated values differ with the observed product name; no perfect identity
extraction or universally correct estimate is claimed.

The Korean fixture remains a semantic observation limitation. The model
drops `리터당` even after the explicit prompt instruction. A separate schema
ordering diagnostic put `price_text` first (confirmed in the actual request),
but returned an empty tag and numeric 1000 in one HTTP call, 10.21 s. That
prototype was withheld. The parser cannot recover unit words absent from the
model observation; this failure is not counted as fixed.

Artifacts under `/workspace/scratch/cpu-vlm-probe-2b/`:

- `capture-unit-before/capture-unit-price-json_schema-1793012909086813013`
- `capture-unit-after/capture-unit-price-json_schema-1793013527868797727`
- `capture-unit-json-after/capture-unit-price-json-1793013939427693122`
- `capture-unit-price-control/capture-price-json_schema-1793013556385442005`
- `capture-unit-krw-before/capture-unit-price-krw-json_schema-1793013370742822243`
- `capture-unit-krw-after/capture-unit-price-krw-json_schema-1793013541745443783`
- `capture-tag-first-diagnostic/capture-unit-price-krw-json_schema-1793013810036416437`

The initial new rate tests failed 52 cases and passed eight against the old
parser. Final capture checks passed **1,381 tests with one optional detector
skip**, 58.67 s, and 95 existing LiteLLM logging cleanup warnings. They include
rates in different currencies, Unicode units/slashes, zero rates, legitimate
per-item prices and preservation of an existing package price. Strict Pyright
reported zero errors/warnings and the app import passed.

This cycle also integrates the interface branch through `bbeaed39`. Its new
roving grid Tab stop disappeared when resizing removed the last visited cell.
The added shrink regression first failed, then passed after selecting an
in-bounds remembered/selected cell or the first cell as the Tab stop. All
**34 grid-editor and empty-floor tests in six files** passed in 6.61 s.
ESLint on 11 changed frontend files, TypeScript checking and the production
build passed (21.66 s; existing chunk/plugin warnings). Probe compilation and
diff checks passed. Changelog conflicts were resolved under Unreleased;
v0.8.2 and earlier changelog content remains byte-for-byte unchanged.
