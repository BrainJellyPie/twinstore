# Staff limits in operations planning

The planner limited newly searched hourly values but initialized its best plan
with the unrestricted current configuration. A request for at most one till or
staff member could therefore return three whenever that existing plan earned
more, or when the search timed out. Existing rosters also bypassed the ceiling.
An offline six-shopper probe reproduced both cases; 17 of 18 initial regression
cases failed, with the uncapped control passing.

The original configuration remains the comparison baseline. The recommendation
starts inside the requested limits, and every candidate and rebuilt roster is
bounded before scoring. Hourly zeroes remain zero. Shift limits apply to total
simultaneous staff across every weekday/hour, retaining existing shift order,
days and duration while reducing/removing excess shift staff. Both daily and
retention outcomes are scored from the exact returned configuration.

Validation:

- 67 staff-limit/roster tests passed in 0.91 seconds. The final focused check
  passed 30 tests in 5.86 seconds: 22 new cases, six existing all-zero staff
  cases and two operations API integration cases (79 distinct tests overall).
- Covered default/all tills, hourly overrides including unsampled hours, crew,
  overlapping/day-specific rosters, two ceilings, expired/short search budgets,
  shift reconstruction, two-week retention, no physical counters, unchanged
  originals and round-trip replay of the returned configuration.
- Strict Pyright passed for the changed planner module.

A constrained recommendation may earn less than the unconstrained baseline.
Roster capping preserves shift durations rather than splitting shifts; the
existing heuristic search does not promise a globally optimal roster.
