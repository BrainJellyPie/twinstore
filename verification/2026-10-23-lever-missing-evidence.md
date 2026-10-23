# Missing evidence in Shelf Lab lever summaries

A failed counterfactual had zero valid pairs and placeholder zero shares, but was
still included in the aggregate effect and bootstrap. Adding failed comparisons
therefore diluted a measured effect toward zero. An entirely failed benchmark
printed zero effects and returned success.

Summaries now include only counterfactuals with at least one valid pair. Genuine
zero effects remain valid observations. The CLI labels unavailable comparisons,
reports the excluded count, and returns status 1 when no usable comparisons exist,
including an empty benchmark. JSONL retains every raw outcome and error count.

Verification:

- Initial reproduction: 24 failed and 3 passed in 2.28 seconds.
- Final targeted run: 50 passed in 3.53 seconds, including related invalid-reply
  and benchmark pick-shift tests. No live model calls.
- Missing comparison counts 1, 2, 9 and 50 across three seeds leave valid means
  and intervals unchanged; all six mixed-kind orderings exclude failed-only kinds.
- Empty, all-failed, partially valid and fully valid CLI runs preserve raw records
  and produce the appropriate exit status. Genuine zero-effect cases stay included.
- Pyright passed for both changed modules.

The existing interval resamples counterfactual effects. Its module description now
states that method accurately; this fix does not introduce respondent-level
uncertainty or correct selection bias from nonrandom model failures.
