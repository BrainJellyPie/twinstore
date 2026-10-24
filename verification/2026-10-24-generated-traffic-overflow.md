# Bound extreme model estimates with observed traffic

Hourly visitor estimates accept nonnegative integers, including very large
structured model outputs. Without supplemental traffic these already reach the
existing population cap. With a fitted traffic profile, weekday/hour weighting
first converted the estimate to float: large estimates lost units and sufficiently
large ones raised `OverflowError`, aborting generation before the cap was applied.

Use rational arithmetic for totals above the exact integer range of a double
(`2**53`). Keep the existing float path and tie ordering for ordinary totals. The
existing caller still applies its population cap; no new visitor limit or model
retry is added, and this does not endorse the model's extreme estimate as real data.

The regression covers powers from 10**30 to 10**1000, with/without weekday scaling,
exact nonnegative apportionment, and a full offline generation pipeline consuming
JSON model output with a valid seven-day traffic profile. The generated population
stays at 1,000, IDs stay unique, only the requested two customers are model-written,
and the remaining twins preserve the 250/750 hourly distribution.

Before: twelve failing cases and two controls passing. After: 212 focused
generation/traffic/upload checks passed in 4.97 seconds. A seeded 250-case parity
probe within those checks preserved ordinary-count results exactly. Strict
Pyright reported zero errors; `git diff --check` passed. No live model calls were
made. This is an adversarial numeric-response case, not the earlier reported
starter-category failure.
