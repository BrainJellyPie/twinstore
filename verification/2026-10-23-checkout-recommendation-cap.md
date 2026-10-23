# Checkout recommendations beyond thirty tills

The recommendation search returned 30 whenever no tested count met the wait
target. For 500 simultaneous one-minute checkouts and a two-minute target, it
recommended 30 even though that capacity produces a 470.4-second average wait.

The search now expands until it finds feasible capacity and bisects to the
minimum count. One till per visit provides a finite zero-wait upper bound.
Cached hourly results are shared across searches, and a heap tracks the next
free till. Days retain separate queues; hourly means still pool their visits.

Verification:

- Initial reproduction: 11 failed and 44 passed in 0.75 seconds.
- Focused capacity, queue and staff-hour checks: 131 passed in 0.78 seconds.
- An added report/JSON round-trip case passed in 0.32 seconds, preserving a
  recommendation of 31 with 31 arrivals and only one installed till.
- Tests cover bursts of 1–2,000 customers, zero/30/120-second targets, empty input,
  zero service, two-day independence and 32 seeded mixtures of basket lengths,
  fractional times, midnight/hour boundaries and service durations. An independent
  cashier schedule confirms feasibility and that one fewer till misses the target.
- Pyright on the changed shared-store module passed.
- Standalone timing: 500 arrivals → 100 tills in 0.0029 seconds; 2,000 → 400 in
  0.0144 seconds; 10,000 → 2,000 in 0.0881 seconds. Each recommendation's computed
  average wait was exactly the 120-second target.

These are theoretical queue-capacity requirements under the existing common-line
model, with abandonment set aside. They do not assert that a floor can fit that
many tills or account for aisle separation or staff refill duties. No layout,
staffing configuration or stored historical report is changed automatically.
