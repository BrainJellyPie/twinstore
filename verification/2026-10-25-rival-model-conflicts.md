# Correct conflicting rival-product matches before pricing

The rival matcher accepted two different listed products for the same rival
name and kept the final row. Reversing a contradictory response could change
the price index from 0.5 to 2 and the suggested rival pull from 1.5 to 0.67.
That result could also be cached and reused for later comparisons.

A request-specific response validator now rejects conflicting valid targets
before acceptance or caching. The existing two-attempt correction budget applies,
and the prompt asks for one match per rival name. Equivalent repeated names,
empty matches and the existing handling of unknown products remain supported.
Repeated failure retains the application's name-only fallback and diagnostic.

Before the fix, 12 conflict cases failed and five controls passed in 2.40 seconds.
Scripted HTTP covers JSON and JSON-schema modes, both row orders, correction,
repeated failures, legacy cache revalidation, later recovery and cached repeats.
The resulting comparison checks the exact price and pull, not just a parsed alias.

After the fix, 56 focused model-match, rival-comparison and rival-pull application
tests passed in 4.53 seconds. Full source Pyright reported zero errors and warnings.
No native inference or paid model calls were used. Remote branches were checked;
the other branches had no new heads since the prior ancestry review.
