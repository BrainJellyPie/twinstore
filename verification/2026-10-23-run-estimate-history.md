# Reliable history for model-work estimates

## Problem and fix

The response cache increments request and cached-request counts but adds no provider tokens. The run
estimator accepted these histories as measurements of future model work, so a cached replay could
produce zero measured tokens, an unknown cost (and no cost warning), and an unrealistically short
runtime. Partially cached runs also understated new work on different shoppers/layouts. Separately,
non-object status/manifest/usage files raised AttributeError, and mixed aware/naive timestamps raised
TypeError, blocking the estimate endpoint.

Select the newest matching run with no cache hits and usable nonnegative token counts. Otherwise use
another eligible run or the existing engine defaults. Ignore wrong-shaped history files. Preserve
valid usage when elapsed time is unusable and use the default pace instead. Legacy histories without
the cache-count field remain supported.

## Focused evidence

- New API matrix covers partial/full cache hits, fallback to an older uncached measurement, five wrong
  JSON shapes in each of three history files, missing/negative/boolean/unknown token values, mixed
  timezone clocks and valid legacy measurements. Uses deterministic offline pricing/resolution.
- Before the fix: **29 failed, 3 passed in 3.28s**.
- New matrix plus existing run-estimate and response-cache modules: **48 passed in 4.14s**.
- Strict Pyright on `application/run_estimate.py`: **0 errors**.

No paid/live model calls, full suite, frontend changes or release binary changes. These remain estimates
of new provider work; actual cache hits can lower the eventual time and charge. No future cache-hit
rate is inferred from past replays.
