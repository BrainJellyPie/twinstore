# POS hourly fidelity uses transaction time

The hourly fidelity metric compared real receipt timestamps against simulated
arrival hours. A visit entering at 10:59:40 and completing checkout at 11:00:25
therefore scored zero similarity against an otherwise matching 11:00 receipt.

The simulated hour now comes from arrival plus the recorded PAY event's elapsed
time and duration. Queue delays already shift PAY events, so no extra wait is
added. Midnight wraps into the next clock day. The metric still compares hourly
shares across the supplied data, not separate calendar-day cohorts.

Legacy buying visits without usable checkout timing are excluded with a report
note. If all buying visits lack timing, the hourly value is unavailable rather
than guessed from arrival. Other sales and basket metrics retain these visits.

## Verification

- Reproduced the original 0.0 score for matching receipt times.
- 24 arrival hours crossed with zero duration, exact-hour completion, immediate
  checkout and an additional hour of elapsed time; datetime arithmetic supplies
  expected clock hours independently.
- Actual shared-store queue replay places one receipt before and another after
  the hour, counting the wait once. Non-buyers, legacy/mixed timelines, unusable
  arrival clocks and stale leave-time summaries are covered.
- Baseline: 79 failed and 24 passed in 1.00 second.
- Final focused engine and API tests: 190 passed in 6.30 seconds. The API test
  generates real offline rule-engine previews and compares their checkout clocks
  with a matching POS export. No paid model calls.
- Pyright for the changed source module: zero errors or warnings.
