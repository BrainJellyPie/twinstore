# Optimization search with incomplete shopper panels

Search cached scalar scores after any nonempty simulation result, even when other
shoppers failed. Removing nonbuyers can inflate revenue per visitor or conversion;
removing long walks can appear to improve walking distance. Those scores cannot be
repaired by pairing results later because search retains only their summaries.

`LayoutEvaluator.evaluate` now rejects recorded shopper failures before incrementing
the evaluation count or caching a score. The existing all-failed error is preserved.
`simulate` and `evaluate_customers` retain partial results because their consumers
explicitly select common successful customers for paired comparisons. Successful
nonbuyers remain valid zero outcomes.

Validation used local rule simulation with selected customer failures, without model
or network calls:

- Before the fix: 36 failures and 3 passes in 2.03 seconds. Cases cover all six
  objectives, panels of 2 and 9, and the first, last, or all but the last shopper
  failing after retries.
- After the fix: 67 focused tests passed in 18.20 seconds, including search behavior,
  cache recovery, successful nonbuyers, and existing vision common-panel/missing-result
  comparisons. Each rejected candidate can be rerun successfully without a stale hit.
- Strict Pyright for the changed engine module: zero errors or warnings.

An incomplete search run now reports its simulation failure rather than publishing
an untrustworthy optimum. This does not retry a whole search or substitute invented
zero-purchase outcomes for failed shoppers.
