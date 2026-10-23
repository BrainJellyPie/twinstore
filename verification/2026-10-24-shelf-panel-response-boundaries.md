# Shelf answers and bounded image preparation

The shelf panel silently converted unknown picked badge numbers to no purchase and discarded
unknown noticed badges. Such malformed model responses entered the paired analysis as valid
refusals or lack of attention, potentially creating a false treatment effect. Both fields now
require actual displayed badge numbers; only an explicit pick of zero means no purchase.
Invalid responses retain an error and follow the existing complete-pair exclusion/reporting
path. Valid refusals, repeated noticed badges and per-SKU deduplication remain supported.

Shelf rendering also ran before acquiring the provider semaphore. With 40 respondents and
two arms, all 80 images were prepared before the first blocked calls could finish, regardless
of the configured concurrency. Rendering and decoding now stay inside the worker slot.

- The initial test fixture incorrectly treated the shape list alias as an enum; corrected
  before measuring the product regression.
- Baseline: 13 failed, 5 passed in 0.50 seconds. Image preparation counted 80 with limits
  1, 3 and 6; invalid badge cases were incorrectly accepted.
- Focused shelf engine/API checks: 33 passed, 21 unrelated cases deselected, in 4.59 seconds.
- Added API checks using real shelf rendering and a fake provider: 2 passed in 5.35 seconds.
  Invalid picks in all responses or one entire arm produce a failed job with no comparison.
- Strict Pyright: zero errors/warnings for the changed module.
- Boundaries include zero/negative/large/nonexistent noticed numbers, invalid picks, valid
  explicit refusals, empty shelves, differing arm inventories and queued image preparation.

No live provider calls or added retry calls. Rendering tests assert work starts, not an
unmeasured memory or latency improvement. No frontend changes or full suite were needed.
