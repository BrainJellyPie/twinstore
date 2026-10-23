# Customer retention keeps the store's operating calendar

After all customers churned, the weekly forecast kept the same staffing plan but
reported zero staff cost. A 14-hour day costing 14,000 became a zero-cost week;
with two crew members, 28,000 disappeared. A weekday losing only its last customer
also vanished from stock-holding costs and the overnight refill/delivery cycle.
This could overstate future profit and change the optimizer's ranking of plans.

The shared-store resolver now optionally takes the original visits as a calendar
reference. The reference supplies modeled weekdays and, for legacy stores without
opening hours, the original observed visit windows. Actual shoppers remain a
separate list: empty days run the store's existing staffing, stock and delivery
logic without introducing synthetic customers. Customer-retention replay supplies
that original calendar each week. Ordinary run resolution keeps its default
behavior, and API identifiers/data schemas are unchanged.

Validation:

- Before repair, the 54-case fixed-cost matrix had **45 failures and 9 passes**,
  0.82 s. Cases vary tills, hourly crew and weekday rosters; one/two modeled days;
  labor/holding cost; unlimited, empty and finite backrooms. Single-day holding
  costs already survived through the old one-day minimum and remain controls.
- Initial engine checks: **657 passed**, 8.54 s, including shared stock, queues,
  rosters and customer retention.
- Extended boundaries and API routes: **119 passed**, 17.29 s. The new engine
  coverage includes full/partial churn, weekday-specific staffing, legacy hours,
  daily deliveries enabled/disabled and preserving original input. An emptied
  Tuesday still refills shelves so Wednesday can use its configured delivery;
  real shopper/checkout counts contain no placeholder visitors.
- Both `/operations/replay` and `/operations/plan` keep staff costs in an empty
  future week. Week-one costs and later fixed costs agree for the same plan.
- Strict backend types: **zero errors/warnings**. App import: **OK, 237 routes**.
- Frontend source is unchanged from the verified main snapshot: 4,479 tests,
  build and lint passed for that exact frontend source.

Full backend verification is running with a durable exit record; its final result
will be recorded before publication. All scenarios use synthetic visits and no
live model calls.
