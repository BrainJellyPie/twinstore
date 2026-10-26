# Preserve shelf observations without treating savings as a selling price

Actual Qwen3.5-2B Q4_K_M CPU inference reproduced two capture defects on
main `a8e5f77f`. The fixtures are 448×512 synthetic product/price-strip
images, directly inspected, not real shop photographs. They exercise the
production VLM label reader and `build_items` using known fixture geometry;
they do not evaluate product detection. llama.cpp b11878 used five CPU
threads, no GPU, an 8,192-token context and fresh application caches.

For `SAVE $1.00`, the model correctly returned that exact tag and a null
numeric price. Conversion nevertheless saved 100 cents as an exact selling
price (one HTTP call, 11.14 s). Recognized savings/coupon/rebate/amount-off
wording now makes that amount unreadable as a selling price, even if the
model also guesses a number. The product and observed text remain available;
the existing catalog estimate is marked estimated. Ordinary tags and explicit
sale prices such as `SALE $1.00` and `Discount price $1.00` still parse.
This is a bounded set of recognized English/Korean/Japanese terms, not a
complete language classifier.

In a separate JSON-mode `$1.00 OFF` run, the model returned the actual
product fields under `properties`, alongside a description. Every value
was discarded by optional-field defaults, leaving an empty product label
(one HTTP call, 15.54 s). The engine response now unwraps actual field
values in that form, keeps flat values authoritative and validates nested
types. Schema definitions are rejected instead of becoming empty success.
Canonical cached labels and the domain/API representation stay flat.
The prompt also distinguishes selling prices from savings and asks the
model to preserve discount words on the tag.

Final actual calls, each with a fresh cache and one HTTP request:

| Tag | Wire mode | Result | Elapsed |
| --- | --- | --- | ---: |
| `$1.00 OFF` | JSON | Product retained; catalog price explicitly estimated | 14.51 s |
| `$1.00` | JSON schema | Exact selling price: 100 cents | 10.63 s |
| `SAVE $1.00` | JSON schema | Product/tag retained; price estimated | 10.63 s |
| `1,000원 할인` | JSON schema | **Still fails**: model omits `할인` from tag text | 10.95 s |

The Korean case remains a semantic OCR limitation: the final model leaves
numeric price null but transcribes only `1,000원`, which the existing parser
accepts as a price. The guard cannot identify a discount word absent from
the observation. No success is claimed for that case, nor for perfect brand
separation (some replies include ACME in the product name). Recorded times
are observations, not a controlled performance comparison.

Artifacts under `/workspace/scratch/cpu-vlm-probe-2b/`:

- Original savings failure:
  `capture-before/capture-saving-json_schema-1793006223604220795`
- Original wrapped-values failure:
  `capture-after/capture-off-json-1793006487741175640`
- Final runs:
  `capture-final/capture-off-json-1793006813844374122`,
  `capture-final/capture-saving-krw-json_schema-1793006831406488950`,
  `capture-final/capture-price-json_schema-1793006845406352436`,
  `capture-final/capture-saving-json_schema-1793006858861968412`

Offline savings regressions first failed 59 cases and passed 12 on the old
converter. Wrapped-response checks first failed ten and passed two on the
old reader. The final focused new cases passed all 83 tests in 2.26 s.
The prior currency test's `$2.49 OFF` control is corrected to `$2.49 EACH`:
currency compatibility does not turn an amount-off tag into a selling price.
The surrounding capture checks and release validation are recorded with
the v0.8.2 release candidate.
