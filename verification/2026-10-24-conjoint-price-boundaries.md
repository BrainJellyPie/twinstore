# Generated conjoint prices must preserve the intended study

The draft converter used binary/banker's rounding and removed the price axis
whenever fewer than two rounded levels remained. USD 1.004 and 1.005 both became
100 cents, and KRW 2.49 and 2.5 both became 2; the result silently had no price
attribute. Small positive prices could become free offers, while an explicit
zero price was discarded. Non-finite/oversized values could crash conversion or
reach the builder as unusable integers. One non-price attribute without prices
could also be returned even though it was not a valid study.

Use Decimal half-up conversion and browser-safe integer bounds. Preserve explicit
zero prices, reject positive prices that round to zero, and reject drafted price
axes with fewer than two distinct rounded levels. Validate the complete normalized
design against ConjointRequest before returning it. Empty prices still mean an
intentionally price-free study with at least two other attributes. Legacy negative
candidates remain ignored when a valid price axis survives.

## Verification

- Reproduced wrong cent/won rounding, lost price axes, invented free offers,
  omitted explicit free options, non-finite/oversized values and unusable designs.
- 43 focused tests passed in 3.22 seconds: conversion, attribute normalization,
  existing negative-candidate compatibility and the draft API's error responses.
- `uv run pyright src/`: 0 errors, 0 warnings.
- Model responses were scripted offline. No frontend changes or live provider calls.

```sh
uv run pytest tests/engine/test_conjoint_price_boundaries.py tests/engine/test_conjoint_design_levels.py tests/server/test_conjoint_design_api.py -q --tb=short
uv run pyright src/
```
