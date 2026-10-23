# Refill quantities respect their scheduled work

A crew refill sized for one missing unit could finish by moving two units when
another shopper bought during that work. At 60 seconds per unit, the store moved
two backroom units in a single 60-second task. A later customer could buy stock
before staff had enough time to put it out, overstating sales and crew capacity.

Each in-progress refill now keeps the unit count used to schedule its work. When
per-unit work is positive, completion moves at most that count; further low-stock
work is dispatched through the existing queue. This keeps already-reserved
checkout appointments intact. With zero per-unit work, the existing fixed time
per face still covers the whole face. Returns and limited backroom stock can
reduce the amount moved, as before.

Validation:

- Before repair, **49 failed / 24 passed**, 1.00 s. The matrix varies 1–3 crew,
  0/1/4/60 seconds per unit, 0/10/60 seconds per face, and finite/unlimited
  backrooms. Recorded work must cover the known replenished units.
- Related engine and API checks: **1,041 passed**, 26.64 s.
- Extended boundaries and API routes: **139 passed**, 17.88 s, including 74 new
  engine cases and two new API cases. A solo cashier finishes two reserved
  checkouts before starting the next refill; each member's tasks do not overlap.
- Two additional randomized checks: **600 cases passed** for paid work coverage,
  utilization, input preservation and observer-independent stock/revenue.
- Strict backend types: **zero errors/warnings**. App import: **OK, 235 routes**
  without the built frontend's two static routes.
- Frontend source is unchanged from the verified snapshot: 4,479 tests, build
  and lint passed for that exact frontend source.

Full backend verification will be recorded before publication. Tests use
synthetic visits and no live model calls.
