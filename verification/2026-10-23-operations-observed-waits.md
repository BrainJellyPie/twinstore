# Recorded checkout waiting and capacity guidance

The results page claimed every hour met the wait target whenever the default till
count exceeded the theoretical recommendation. That comparison ignored actual
delays from staffing schedules, refill work and separated checkout access. It
could also claim failure despite observed waits meeting the target, for example
when impatient shoppers had already left.

Advice now compares the largest recorded hourly mean with the target. Capacity
highlights use the hour's open tills, falling back to the default only for legacy
reports without that field. The capacity table explains its common-line,
checkout-only staffing and no-abandonment assumptions. All copy is localized in
six languages. A small excess that rounds to the target is stated in seconds so
the warning does not display identical rounded durations.

Verification:

- Initial seven-case reproduction failed in 122 ms of test execution.
- The first related run passed 161 cases and failed one artificial fixture with
  zero default counters but installed tills and hourly queues. Current reports
  cannot produce that combination; the fixture was removed without changing the
  existing no-till behavior.
- Final shared-store UI suite: 117 passed (1.82 seconds of test execution,
  5.69 seconds overall). Combined with the 44 catalog checks already passed,
  161 unique relevant cases passed.
- Covers insufficient staffing, refill-style delays despite sufficient nominal
  capacity, a different worst-wait/recommended-capacity hour, actual waits at or
  below target, 0.1-second excesses, zero/hourly/legacy staff counts and all locales.
- TypeScript and changed-file ESLint passed. Production build passed in 17.66
  seconds with existing chunk-size/plugin-time warnings.

Recorded hourly means still aggregate the modeled days. This change does not
claim that every individual shopper met the target, and it does not alter runs.
