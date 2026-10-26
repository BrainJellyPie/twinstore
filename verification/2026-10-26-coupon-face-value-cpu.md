# Coupon face values are not product selling prices

On main `d28e13fa`, actual Qwen3.5-2B CPU inference correctly transcribed
`$1.00 COUPON` from a synthetic shelf tag. The model left its numeric price
unknown, but the downstream converter treated the coupon's $1 face value
as a 100-cent exact product price. This could overwrite an existing product
price when placing the capture. The baseline took two HTTP requests and
14.92 seconds, with zero application cache hits.

The existing savings-amount suffix guard now recognizes an amount followed
by bare `coupon`/`coupon value`, including plural and terminal punctuation.
Such a tag retains its literal text and uses the existing estimated-price
path; placing an estimated capture retains a matched product's known price.
The suffix is anchored so `WITH COUPON`, `COUPON PRICE`, `coupon applied`,
`after coupon` and `including coupon` still identify a stated selling price.
The OCR prompt, numeric-model output, retry limits and existing FREE-tag
policy are unchanged.

## Actual model checks

Qwen3.5-2B Q4_K_M with its vision projector, llama.cpp b11878, five CPU
threads, no GPU, 8,192-token context and reasoning disabled. Both the package
and separate price strip go through production `VLMLabeler`, followed by
`build_items`. Fixtures are generated images with known geometry, inspected
visually; these checks do not benchmark detection or real shelf photography.

| Printed tag | Mode | Seconds | Final result |
| --- | --- | ---: | --- |
| `$1.00 COUPON` | Native schema | 4.33 | Literal retained; fallback marked estimated |
| `$1.00 COUPON` | JSON | 17.41 | Literal retained; fallback marked estimated |
| `$1.00 WITH COUPON` | Native schema | 14.52 | Exact price 100 cents |
| `FREE $0.00` | Native schema | 13.46 | Exact price zero |

All four final cases pass, each with two HTTP calls and zero application
cache hits. The fallback amount differs with the model's category/name
classification (229 versus 189 cents); it is not claimed as a read price.
Observed times include possible server prefix reuse and are not benchmarks.
The reusable probe adds `capture-coupon-value`.

## Regression checks

Before the guard, the expanded savings suite has 25 failing cases and 144
passing controls. The final focused price suite passes 1,293 tests in 4.08
seconds across nine files. Coverage includes coupon suffixes, currency
codes/symbols, full-width text, zero coupon values, numeric guesses,
conditional sale-price controls, estimated capture, preservation of an
existing 799-cent offer, ordinary prices, deposits, unit rates, multipacks,
free numeric tags and unsafe amounts. Strict Pyright reports zero
errors/warnings; server import/boot, probe compilation and diff checks pass.
The 39 existing LiteLLM logging cleanup warnings remain.

Frontend files are unchanged from `d28e13fa`; its 152 passing tests,
TypeScript, changed-file lint and build remain the applicable evidence.
The published v0.8.2 assets remain unchanged.

## Other observations kept separate

The execution environment disconnected before the first `FREE`-only image
probe reached the model (zero calls). After reconnecting and restarting the
same CPU server, the model read `FREE` correctly, but the existing numeric-
price requirement produced an estimated 229-cent value. A scratch diagnostic
expecting zero failed; this remains a separate limitation, and no change to
that policy or its tests is claimed here.

Three preceding never-free-shipping prompt candidates were withheld. One
kept falsely claiming that every order would pay shipping; one returned an
empty patch/question but contradicted itself about whether a numeric
threshold could change; one set the threshold to zero, making shipping
free instead. No candidate was committed. The existing unapplied-threshold
warning remains in production.

Artifacts under `/workspace/scratch/cpu-vlm-probe-2b/`:

- Coupon baseline: `price-word-baseline/capture-coupon-value-json_schema-1793035952444990779`.
- Final calls: `coupon-suffix-final/capture-*/result.json`, timestamps
  `1793036100612903521`, `1793036107998632915`, `1793036128401375289`, `1793036145746832350`.
- FREE-only observation: `price-word-baseline/capture-free-word-json_schema-1793035934946460499`.
- Interrupted initial attempt: `free-word-baseline/capture-free-word-json_schema-1793035771681022795`.

Logs: `/workspace/scratch/coupon-suffix-{before,tests,pyright,boot}.log`.
Withheld prompt review: `/workspace/scratch/no-free-policy-review.json`.
