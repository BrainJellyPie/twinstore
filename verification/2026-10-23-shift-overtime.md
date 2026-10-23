# Work crossing a shift boundary stays in labor cost

A cashier scheduled 08:00–09:00 could serve a shopper until 09:09:55 while the
replay charged only one hour. The same omission affected hourly crews, weekday
rosters and shelf refills. A planner could therefore favor a shift ending before
its work actually finished.

The resolver adds the portion of each work interval outside that worker's
scheduled hours. Normal scheduled time remains counted once. If only some staff
leave, only their ongoing work adds overtime; a shelf-only worker does not add
till capacity. Queue admission, task dispatch and customer timelines stay the
same. The existing rule keeping the final roster shift after store closing also
continues without double payment.

Validation:

- Before repair, **48 failed / 72 passed**, 0.56 s, across till-only staffing,
  hourly crews and rosters; 1–3 staff; checkout/refill work ending exactly at,
  before or after the shift boundary; and multiple shoppers.
- Initial related engine checks: **800 passed**, 5.65 s, including stock,
  checkout closing time and customer-retention calendars.
- Extended boundaries and API routes: **220 passed**, 20.43 s. The 159 new engine
  cases also check partial staffing reductions and a 90-minute checkout crossing
  an unstaffed hour into a later shift. Three API cases report 1.17 hours and
  labor cost 1,170 at 1,000/hour for work ending 09:09:55.
- Strict backend types: **zero errors/warnings**. App import: **OK, 235 routes**
  without the built frontend's two static routes.
- Frontend source is unchanged from the verified snapshot: 4,479 tests, build
  and lint passed for that exact frontend source.

- Additional stress check: **300 randomized cases passed**, varying hourly and
  roster staffing, till count, finite stock, service times and shelf work. Paid
  time covers completed work, till utilization stays at or below 100%, and input
  visits remain unchanged.
- Full backend suite: **26,479 passed, 1 skipped**, 1,149.19 s (19m09s), exit 0.
  The durable runner verified source commit `48f3ee7`; this final record changes
  documentation only.

Scenarios are synthetic and make no live model calls.
