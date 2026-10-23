# Report the staff serving checkouts after closing

## Reproduction and change

With one crew member scheduled 08:00–22:00, a shopper entering at 21:59:50
reaches checkout at 22:00:15. The existing simulation correctly keeps the last
shift to serve that shopper and records the purchase. The hourly report
recomputed staffing from the normal 22:00 roster, however, and reported zero
crew and zero open tills for that paid checkout. Closing at midnight had the
same mismatch in the `00` hour.

Record effective crew and till counts when each checkout enters the queue,
using the simulation's existing closing-shift policy. Include these observations
in hourly staffing maxima along with the existing maximum over simulated
weekdays. This changes reporting only; queue order, service, overtime costs,
abandonment and inventory behavior are unchanged. Physical till limits remain
applied even when more crew are on duty.

## Verification

- Baseline: 28 failures and 2 passing controls in 0.83 seconds.
- New regression cases cover all seven weekdays, closing at 22:00 and midnight,
  one worker/one till, three workers/two tills, before/after closing in one run,
  report JSON round-trips and unchanged input shoppers.
- A genuinely unstaffed closing shift still reports zero and abandons the basket.
  The existing maximum-over-weekdays aggregation remains intact, including hours
  with different staffing on different simulated days.
- 807 checks in four focused checkout/shared-store/overtime modules passed in
  7.26 seconds. Changed-module Pyright reported zero errors/warnings.
- No frontend rebuild, full test-suite run or paid model calls.
