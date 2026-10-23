# Prepare the town days that a run actually uses

Town runs previously built every weekday in the saved population, even when the scenario
selected just Friday. The later run filter discarded the other visitors after all demand,
arrival and context work. Identical consecutive weekdays also repeated the full demand
calculation before drawing their independently seeded arrivals.

Day filtering now happens before preparation. The full persona pool remains available, so
an age absent from the selected day can still use its example from another day. The previous
demand report is reused only for an equal day profile and equal opening-hour list within the
same call. Only one demand report is retained; changed hours/profiles recompute it. Customer
and origin draws retain their original per-day seeds.

- Baseline regression: 8 failed in 2.37 seconds, including unmatched selected days, partial
  weeks, different schedules and a weekend-profile scenario applied to the full week.
- Focused checks: 35 passed in 8.40 seconds; strict Pyright zero errors/warnings.
- Twelve before/after run-input hashes agree exactly, including complete customer records
  and kept arrival annotations: two operating schedules, three scenarios, capped/uncapped.
- Dense 3 km town (seed 24102490), seven-day pool, Friday scenario and a 30-customer cap:
  local preparation fell from 13.541 to 1.942 seconds; both produce 30 shoppers.
- The older day-profile test now expects one demand call per distinct consecutive profile;
  its checks of scenario traffic multipliers and store-format effects remain in place.

No provider calls, frontend changes or full suite. Benchmarks use one OpenBLAS thread locally;
they describe input preparation rather than the following shopper simulation or model latency.
