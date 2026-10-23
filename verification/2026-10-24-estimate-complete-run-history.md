# Keep failed shopper histories out of normal-run estimates

A run can finish with successful results for only part of its requested population. Its
completed-customer counter counts settled shoppers, including failures and skipped work.
The cost estimator divided the reduced provider work by that entire counter, making the
next healthy run look cheaper and faster and potentially suppressing the existing warning.

Measurements now require a completed run with zero failed customers, in addition to the
existing uncached/valid-token requirements. A failure count that is present but malformed
is also unusable. Legacy records without that field remain supported. The newest usable
older measurement wins, or the existing engine defaults apply when none is available.

- Baseline regression: 12 failed in 3.21 seconds.
- Focused history, ensemble and estimate API checks: 82 passed in 3.78 seconds.
- Strict Pyright: zero errors/warnings.
- Cases cover partial failures, mostly failed populations, malformed counts and both an
  older clean measurement and default fallback. Existing valid/legacy history tests pass.

No provider calls, frontend changes or full suite. The finished run's actual results and
failure reporting remain available; only reuse as a forecast measurement changes.
