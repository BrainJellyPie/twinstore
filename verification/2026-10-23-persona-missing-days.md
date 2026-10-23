# Preserve complete customer populations across model failures

## Reproduction and fix

An offline model estimated ten visitors for Monday, Tuesday and Sunday, then returned an empty Tuesday
customer batch. Generation succeeded with only Monday/Sunday customers while retaining all three
daily visitor estimates. Provider failures confined to one day had the same outcome: the global
failure threshold did not notice that the entire day was missing.

`PersonaBatch` now requires at least one customer, so empty responses use the existing structured
response retry budget. After all days settle, generation rejects any positive-estimate day without
customers. The existing majority-failure check retains precedence. A failed probe stops before the
write-size decision; a partially failed day can still fill its population from that day's successes.
Days calibrated to zero visitors and closed days do not require a generated customer.

## Evidence

- New tests cover empty/provider failures on Monday/Tuesday/Sunday, full and one-customer samples,
  failed probes, short nonempty batches, partially failed days, zero calibrated traffic and closed days.
- The actual background worker runs with an offline model and temporary project storage. On either
  failure type it marks generation failed, names Tuesday and preserves saved customers and estimates.
- Before the fix: **16 failed, 5 passed in 2.76s**.
- Four relevant modules: **79 passed, 1 failed in 4.21s**. The remaining old pacing test deliberately
  returned no customers for a positive day; updated its stub to return a valid customer while retaining
  the original pacing assertions. That test then **passed in 2.17s**. Total: **80 distinct cases passed**.
- Strict Pyright on `engine/generators/persona.py`: **0 errors**.

No live model calls, full suite, frontend changes or release binary changes. Existing saved populations
are not migrated; this protects newly generated populations.
