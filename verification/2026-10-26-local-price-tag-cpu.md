# Read local price tags separately without losing the product

The existing Korean fixture `리터당 1,000원` exposed a remaining observation
failure: the small model dropped `리터당` and returned an apparently ordinary
1,000-won price. The converter cannot recover a qualifier absent from its
input. The earlier actual before/after failures are recorded in
[the unit-rate investigation](2026-10-26-capture-unit-rates-cpu.md).

A new full-visible-text-first prototype also failed: in one actual native
JSON Schema call, 12.15 seconds, its extra field contained only the product
text and its price still omitted `리터당`. That prompt/schema prototype was
withheld. A separate price-strip transcription preserved the qualifier and
also passed Korean savings and ordinary selling-price controls, leading to
the implemented change.

For loopback model endpoints, capture now reads the existing combined product
view, then transcribes its visible price strip in one additional bounded
single-field task. The second reading supplies literal price text; the
combined reading's numeric guess is discarded. Existing price conversion
handles currency, selling prices, savings, rates and multipacks. A missing
strip, failed request or invalid transcription leaves the price unknown
while retaining product identity. Logical call counts include the extra read,
and both requests use the existing cache and concurrency limits.

Cloud/non-loopback capture keeps the combined reader. Its response schema
was compared byte-for-byte with the prior schema and is unchanged. The domain
label accepts up to 200 characters of separately transcribed tag text so a
long qualifier is not cut off; the combined response retains its prior
24-character bound. No extra tag request is made for a strip outside the
photo. The production crop helper now returns both the combined view and
its actual visible strip, rather than guessing a fixed boundary in user
photos.

The CPU probes use known 448×512 synthetic composite fixtures, not retail
photographs. The separate fixture strip is the known region below y=400;
this tests production label reading and conversion, not shelf detection.
The extraction tests independently cover actual production crop boundaries,
missing strips, tilted/border cases and source-image preservation. The model
is Qwen3.5-2B Q4_K_M on llama.cpp b11878, five CPU threads, no GPU, context
8,192. Final cases use the implemented language instruction, not the earlier
scratch prototype. Every final case made two actual HTTP requests with zero
application cache hits. Server prefix reuse was possible, so the timings are
not a speed benchmark. Catalog fallbacks remain estimates.

| Printed tag / package | Wire mode | Result | Time |
| --- | --- | --- | ---: |
| `리터당 1,000원` | `json_schema` | Estimated fallback | 13.96 s |
| `1,000원 할인` | `json_schema` | Estimated fallback | 13.10 s |
| `1,000원` | `json_schema` | 1000 won exact | 13.41 s |
| `$1.00` | `json_schema` | 100 cents exact | 13.17 s |
| `리터당 1,000원` | `json_object` | Estimated fallback | 17.85 s |
| `$1.00 / BOTTLE` / 6 BOTTLES | `json_schema` | Estimated fallback | 14.01 s |
| `FREE $0.00` | `json_schema` | 0 cents exact | 15.01 s |
| `(blank)` | `json_schema` | Estimated fallback | 13.61 s |
| `$6.00 / PACK` / 6 PACK | `json_schema` | 600 cents exact | 13.16 s |
| `$1.00 WITH COUPON` | `json_schema` | 100 cents exact | 14.18 s |

The probe now saves each actual request image separately and records its
filename in the trace. Previously every image reference said `image.png`,
which was adequate for the single composite but ambiguous after introducing
a second view. An additional native Korean unit-rate run verifies the exact
transmitted composite and tag images. Earlier functional runs retain their
known fixture and result but do not have those per-request image files.
Capture probes default to the new local behavior; `--no-separate-price-tag`
explicitly selects the unchanged combined reader for comparisons.

Focused validation passed **1,390 tests in 15 files in 17.06 seconds**, with
95 warnings of the existing LiteLLM logging-cleanup kind. The earlier new-tag
and border-crop run passed 67 tests in 44.15 seconds; its overlapping tests
are not added to the total. Coverage includes native/JSON request shape,
both request caches, exact free/selling prices, Korean rates/savings,
multipack rates, long qualifiers, empty/null/invalid/too-long tags, request
failure, product preservation and automatic loopback-only application wiring.
Strict Pyright returned zero errors/warnings and app import passed. Probe
compilation and diff checks passed. Frontend code is unchanged; released
v0.8.2 changelog content is retained.

This resolves the tested qualifier omissions by separating the visible
evidence. It is not a guarantee for arbitrary fonts, shelf geometry, blurred
photos or other models. A visible strip adds one model task per product
group; failures remain estimated rather than reverting to an unverified
combined-image amount.

Artifacts under `/workspace/scratch/cpu-vlm-probe-2b/`:

- `capture-local-tag-final-capture-unit-price-krw-json_schema/capture-unit-price-krw-json_schema-1793022439421999540`
- `capture-local-tag-final-capture-saving-krw-json_schema/capture-saving-krw-json_schema-1793022456288047705`
- `capture-local-tag-final-capture-price-krw-json_schema/capture-price-krw-json_schema-1793022472369464234`
- `capture-local-tag-final-capture-price-json_schema/capture-price-json_schema-1793022488795552863`
- `capture-local-tag-final-capture-unit-price-krw-json/capture-unit-price-krw-json-1793022504624772038`
- `capture-local-tag-final-capture-container-count-price-json_schema/capture-container-count-price-json_schema-1793022525222644150`
- `capture-local-tag-final-capture-free-price-json_schema/capture-free-price-json_schema-1793022542026165535`
- `capture-local-tag-final-capture-blank-price-json_schema/capture-blank-price-json_schema-1793022559986480560`
- `capture-local-tag-final-capture-pack-price-json_schema/capture-pack-price-json_schema-1793022576256677928`
- `capture-local-tag-final-capture-coupon-price-json_schema/capture-coupon-price-json_schema-1793022612300493718`
- `capture-local-tag-wire-evidence/capture-unit-price-krw-json_schema-1793022833155186228`
- `capture-visible-text-unit-diagnostic/capture-unit-price-krw-json_schema-1793021455269640624`

The additional wire-image run passed in 13.78 seconds with two actual
HTTP requests and no application cache hits; both saved PNG inputs were
inspected directly (448×512 composite and 448×112 tag).
