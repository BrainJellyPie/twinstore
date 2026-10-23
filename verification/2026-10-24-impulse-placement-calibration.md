# Selected shelf heights in impulse calibration

Actions already retained the selected block/level, but timeline construction discarded both.
`impulse_profile` then assigned every purchase of the same rack/face/SKU to its first stored
slot. With identical tea on four levels, choosing level 4 could train the optimizer against
level 1; reordering the slots changed the target despite the same purchase.

Purchase timelines now store optional block/level fields from the resolved slot. They survive
JSON storage and shared-store quantity reductions. Calibration uses that evidence; legacy
records infer a level only if the candidate levels are unique. Unattributed purchases still
count toward impulse rate and revenue share, but not the normalized height distribution.

Shared-store substitution pools stock by rack/face/SKU and does not select an exact replacement
slot. It clears the original product's location fields; unique replacement heights can still
be inferred. The stock pooling and substitution policy are unchanged. Existing saved files
load with absent fields defaulting to null; no history is rewritten.

- Baseline: 69 failures, 4 passes in 0.82 seconds. Failures cover wrong profile attribution,
  missing persisted evidence, ambiguous legacy records and substitution/partial-stock paths.
- Routing/timeline, all four faces, four heights, two blocks, reversed slot order, legacy
  inference, shared inventory and fake VLM/ensemble checks: 868 passed in 6.62 seconds.
- Existing full rule-surrogate calibration fixture: 1 passed in 8.60 seconds; its fit still
  reduces the pilot gap and increases impulse propensity as expected.
- Strict Pyright for all four changed source modules: zero errors/warnings.
- No live model calls, frontend changes, full suite or release asset changes.
