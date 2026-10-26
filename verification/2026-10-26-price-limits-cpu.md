# Advertised limits are not exact selling prices

Actual CPU runs on main `80a283f5` read `FROM $1.00`, `UNDER $1.00`
and `1,000원부터` correctly and returned null numeric prices. Conversion
nevertheless saved exact prices of 100 cents, 100 cents and 1,000 won.
The parser treated a lower or upper bound as this product's selling price.

Conversion now rejects recognized price-limit prefixes/suffixes and
comparison marks before amount conversion. Numeric model guesses cannot
bypass the printed limit. Product identity and printed text survive, the
usual fallback is estimated, and an existing matched product retains its
price when the capture is placed. Ordinary cash prices, zero-dollar prices,
product names such as Fromage, and explicit prices plus tax/deposit retain
their current interpretation. Model prompts and output schemas are unchanged.

## Actual CPU observations

Qwen3.5-2B Q4_K_M on llama.cpp b11878, five CPU threads, no GPU,
8,192-token context, reasoning disabled. Every row used two HTTP requests
and zero application cache hits. Images were inspected visually. Known
synthetic geometry isolates recognition/conversion, not shelf detection.
Elapsed times are observations, not comparative performance measurements.

| Tag | Mode | Seconds | Result |
| --- | --- | ---: | --- |
| FROM $1.00 baseline | Native schema | 13.36 | Incorrect exact 100 cents |
| UNDER $1.00 baseline | Native schema | 13.50 | Incorrect exact 100 cents |
| 1,000원부터 baseline | Native schema | 13.25 | Incorrect exact 1,000 won |
| FROM $1.00 repaired | Native schema | 13.56 | Estimated 229 cents |
| 1,000원부터 repaired | Native schema | 13.35 | Estimated 2,600 won |
| UNDER $1.00 repaired | JSON | 17.86 | Estimated 189 cents |
| FROM $1.00 repaired | JSON | 13.35 | Estimated 189 cents |
| $1.00 positive control | Native schema | 14.47 | Exact 100 cents retained |

Estimated amounts vary with product/category interpretation; they are not
prices recovered from the advertised limits. The three limit fixtures are
retained as reusable probe cases.

## Regression checks and integration

The new file fails 123 cases and passes 13 against the parent; all 136 pass
after repair. It covers numeric guesses, zero, fullwidth text, comparison
signs, cents, Korean/Japanese/Chinese labels, ordinary-price controls and
capture placement with/without an existing product. Source stores and
unrelated shelves remain unchanged. Final checks pass 1,601 cases across
ten capture files in 4.23 seconds. Thirty-nine existing LiteLLM asynchronous
logging cleanup warnings remain. Strict Pyright reports zero errors and
warnings; server boot, probe compilation and diff checks pass. Frontend
code is unchanged and inherits the preceding 138 UI cases/type/lint/build.

Also records branch `claude/online-shopping-features-ji7y0f` through
`be2d6f6e`, whose new commit only merges already-integrated main work into
that branch. The changelog ordering conflict retains main's complete
Unreleased text. This adds no further application change. Released changelog
text and v0.8.2 assets/tag remain unchanged.

Evidence: `/workspace/scratch/cpu-vlm-probe-2b/price-bound-baseline/`
(three result records, timestamps 1793041930540754827–1793041963385655023)
and `price-bound-final/` (five result records,
1793042054532857674–1793042124250377286).
Logs: `/workspace/scratch/price-bound-{baseline-cpu,final-cpu,before,unit-tests,tests,pyright,boot}.log`.
