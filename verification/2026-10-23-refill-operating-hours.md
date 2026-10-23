# Regular refills follow the store's operating hours

The periodic refill loop stopped at the last planned visitor's departure even
when the store remained open. In a two-day example, adding one nonbuying observer
on Monday changed Tuesday's available stock and raised total sales from 900 to
1,200: only the observer caused Monday's scheduled refill to run, which then
triggered Tuesday's morning delivery. A late visitor could conversely trigger
a refill at closing, after refill crews were supposed to stop.

Periodic refills now use the store's existing closing boundary, already used by
crew dispatch. For stores without opening hours, that boundary remains the
observed visit window. Refills still only count as a round when stock moves.

Validation:

- Before repair, **63 failed / 3 passed**, 0.69 s. The 60-case observer matrix
  varies 30/60/120/240/360-minute intervals, 1–3 shelf units, 1–2 backroom units
  and deliveries enabled/disabled. Controls cover exact closing boundaries,
  visitors staying after closing and legacy stores without hours.
- Initial combined engine/API checks: **1,013 passed / 2 failed**, 28.35 s.
  Both failures expected a shelf emptied at 10:31 to remain empty until 22:00,
  omitting its 11:00 refill. Those expectations now end the empty spell at 11:00
  and count the two actual refill rounds.
- Updated shared-store and boundary checks plus API routes: **673 passed**,
  22.74 s. The two API cases verify the delivery-dependent sales and refill cost.
- Strict backend types: **zero errors/warnings**. App import: **OK, 235 routes**
  without the built frontend's two static routes.
- Frontend source is unchanged from the verified snapshot: 4,479 tests, build
  and lint passed for that exact frontend source.

- Additional stress check: **300 randomized observer-invariance cases passed**,
  across crew/till modes, stock levels, deliveries, substitution and service
  times. Nonbuying observers leave stock, revenue and other visits unchanged.
- Full backend suite: **26,547 passed, 1 skipped**, 1,137.18 s (18m57s), exit 0.
  The durable runner verified source commit `f88118e`; this final record changes
  documentation only.

All fixtures use synthetic visits and no live model calls.
