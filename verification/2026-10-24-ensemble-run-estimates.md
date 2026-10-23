# Ensemble work and cost before running shoppers

The estimate treated every ensemble as one model and averaged member prices, regardless of
mixture weights or vote fan-out. Vision entrance plans and glances both ask every voter;
text-only engines use mixture even when vote is requested. Six equal-priced voters could
therefore show one sixth of their expected provider work and omit the existing cost warning.

Default vision work now expands by the voter count. Mixture costs use normalized weights,
including finite weights whose sum overflows and subnormal weights. Recorded aggregate token
usage and request counts already include member work and are not expanded a second time.
Mixed local/cloud runs price the cloud share and retain local capacity estimates; unknown
cloud prices remain unknown. Models sharing a local endpoint share its estimated capacity.
A cloud provider's explicit concurrency limit affects pace, not whether it is paid.

- Initial boundary regression: 21 failed, 5 passed in 3.15 seconds.
- First focused verification: 162 passed in 4.59 seconds; strict Pyright zero errors/warnings.
- Additional shared-capacity/concurrency regression: 3 failed in 2.31 seconds.
- Final affected suite: 165 passed in 4.01 seconds; strict Pyright zero errors/warnings.
- Cases cover single/repeated voters, mixture versus vision/text vote, skewed/extreme weights,
  known/unknown/local prices, mixed backends, recorded usage with/without request counts,
  shared local servers, restricted cloud concurrency and crossing the cost warning threshold.

These remain estimates: historical aggregate tokens are apportioned by configured mixture
weights or equal voter shares, not by measured per-member token lengths. Default runtime uses
approximate request durations and capacities; a compatible uncached run's measured pace wins.
No provider calls, frontend changes or full suite were required.
