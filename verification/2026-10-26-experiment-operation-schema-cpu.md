# Require the right fields in automatic A/B draft operations

On main `71c472c2`, the actual CPU model failed to draft two simple Tea
variants: 20% off versus a `1+1` sign. In native JSON-schema mode, both
responses put `Tea` in `category` instead of `product`; the sign variant
also omitted `promo`. Both variants were discarded as untargeted. The
second attempt repeated the first response exactly, and the draft failed
after two HTTP requests (28.14 seconds).

The old `_Change` wire schema required only `kind`. All targets and values
were optional, so its grammar permitted the incomplete operations. The
schema now describes a separate object for each of the six existing kinds:
price, discount, promo, move, package and category_price. Each requires its
own target and operational value, and excludes unrelated fields. Existing
text lengths and numeric bounds are retained; prices are nonnegative and
discounts negative. Zero price and -100% discount remain expressible. Move
level remains optional, preserving the existing eye-level default.

This changes schema generation, not the stored draft representation or the
application's target resolution, currency conversion, edits, engine choice,
prompt wording, output budget or retry count. Canonical cache records and
older replies with unused null fields still pass the existing Python
validation/normalization path. The changed schema naturally changes the
content-addressed cache key. Unknown or ambiguous targets are not guessed.

## Actual CPU results

Qwen3.5-2B Q4_K_M, llama.cpp b11878, five CPU threads, no GPU, 8,192-token
context, reasoning disabled. The client uses the application's A/B draft
temperature 0.2, 6,144-token ceiling and two-attempt limit. Seven final
fresh-cache executions all complete in one HTTP request with zero cache
hits. Each draft is applied through production `apply_changes` to an
isolated fixture; no saved user store is modified.

| Request | Mode | Time | Verified effect |
| --- | --- | ---: | --- |
| 20% discount versus `1+1` | Native schema | 8.41 s | Two Tea variants: 159 cents with 199-cent reference; sign with unchanged 199-cent price |
| Same discount/sign request | JSON | 20.12 s | Same requested effects |
| Korean fixed-price/discount request | Native schema | 11.72 s | 1,500-won price versus 1,592-won discounted price, both retaining 1,990-won reference |
| 100% versus 20% discount | Native schema | 8.43 s | Zero versus 159 cents, both retaining 199-cent reference |
| Move only Tea to Endcap, level 3 | Native schema | 5.87 s | Correct destination/level; prices and other products preserved |
| Replace only Tea's package | Native schema | 6.66 s | Correct listed package identifier; other fields preserved |
| Reduce Drinks shelf by 10% | Native schema | 7.50 s | Tea 179 cents, Water 89 cents, original references retained; other shelf unchanged |

These are draft/edit checks, not shopper simulation results or evidence of
real-world sales effects. All model calls here are text-only. The package
case uses a listed identifier and fixture URI; it does not test image
interpretation. Times are observations, not benchmarks; the server can
reuse prompt prefixes independently of the application cache.

The committed `local-experiment-probe.py` checks complete product fields and
placements, and preserves the source layout. Its first four cases were also
rechecked using the saved real-model cache entries: four successful replays,
zero additional HTTP requests, one cache hit each. The final three cases
ran directly through that reusable probe.

## Correcting a probe assumption

The original JSON baseline already produced the correct two operations.
An early scratch assertion nevertheless marked it failed because the model
chose `rule` rather than `vlm`. The application supports a generic sign
impulse boost with rule shoppers and reports that limitation in experiment
notes. Requiring vision for every sign was an incorrect probe criterion.
The same false negative affected the first schema prototype. Their raw
results remain unchanged, with separate reanalysis records; the final probe
reports this engine caveat without calling valid operations a schema failure.
No claim is made that rule shoppers interpret the literal `1+1` sign.

## Automated checks and evidence

Twelve new SDK/HTTP regressions cover all six operation kinds in both JSON
modes. Every case fails against the frozen main schema and passes after the
change. The tests validate the actual transmitted schema, required targets
and values, unrelated/mixed fields, null/empty fields, currency-compatible
zero prices, -100%/fractional discounts, invalid numeric types, shelf-level
bounds, successful application and canonical cache replay.

The focused suite passes 193 tests across seven files in 7.12 seconds,
including prior draft recovery, output-budget, repeated-offer and currency
tests. A separate compatibility pass covers bounded names, optional/unused
fields, multiple targets and accessible shelf faces: 254 tests across five
files in 5.71 seconds. Together these are 447 tests, without repeating the
first group. Strict Pyright reports zero errors/warnings, server import/boot and
probe compilation pass. Frontend code and the published v0.8.2 release are
unchanged. Existing LiteLLM asynchronous logging cleanup warnings remain.

Artifacts under `/workspace/scratch/cpu-vlm-probe-2b/`:

- Failed native baseline: `ab-discount-promo-json_schema-1793032211197709863`.
- Original JSON (correct operations, false engine failure): `ab-discount-promo-json-1793032250478675946`.
- Scratch prototype (same false engine failure): `ab-discount-promo-json_schema-1793032338150562014`.
- Final native discount/sign: `ab-discount-promo-json_schema-1793032473089245186`.
- Final JSON discount/sign: `ab-discount-promo-json-1793032567773382115`.
- Final KRW: `ab-fixed-price-krw-json_schema-1793032590560661986`.
- Final free discount: `ab-free-discount-json_schema-1793032605425387278`.
- Final move: `ab-operation-final/ab-move-json_schema-1793032812165431854`.
- Final package: `ab-operation-final/ab-package-json_schema-1793032820567034697`.
- Final category: `ab-operation-final/ab-category-json_schema-1793032829683400489`.
- Saved-output checks: `ab-operation-replay/ab-*-1793032907759980541` through `ab-*-1793032915263233232`.

Logs: `/workspace/scratch/experiment-schema-{tests-parent,new-tests,focused-tests,compatibility-tests,pyright,boot}.log`.
Reanalysis: `/workspace/scratch/ab-discount-promo-json-reanalysis.json` and
`ab-required-schema-prototype-reanalysis.json`.
