# Requested roster limits on existing shifts

An existing roster could survive **Plan a roster of shifts** outside its requested
length limits: a two-hour shift stayed two hours and a fourteen-hour shift stayed
fourteen, even when the operator explicitly requested four-to-eight-hour shifts.
The search only tried one-hour adjustments and accepted cheaper outcomes, so it
could neither bridge a large length difference nor accept a necessary increase in
labor to meet the new requirement. Ten of twelve initial regression cases failed;
the nine-hour cases could already shorten to eight in one step.

When explicit limits invalidate an existing roster, planning now builds a feasible
starting roster first, using each weekday's current staffing and opening hours.
Matching shifts are combined across weekdays; duplicate large staffing groups stay
separate to respect the 100-person per-shift bound. Closed and unspecified weekdays
remain unstaffed. Removing every shift outside operating hours keeps an explicit
zero-staff schedule instead of accidentally restoring the default crew.

The planner then compares money among feasible changes. Mandatory length limits can
cost more than the old, invalid plan, so the original outcome remains visible for
comparison. A valid existing roster retains the original search behavior. The
returned rebuilt configuration is validated, including the 60-shift storage limit.

A second boundary returned a one-hour shift for a four-hour minimum when the store
opened for only one hour. Such requests now return an actionable 422 response to
lower the minimum or extend opening hours; a zero-staff window needs no shift.
No frontend/API identifiers or paid-model behavior changed.

Validation on the isolated `fix/roster-limits-20261023` worktree:

- Initial 12-case reproduction: **10 failed, 2 passed**, 0.31 s; after repair:
  **12 passed**, 0.39 s.
- Shared-store engine and new roster suite: **593 passed**, 5.62 s.
- Roster and actual API-route checks: **104 passed**, 22.02 s. This includes invalid
  operating-window responses and saving/replaying a newly constrained roster.
- New committed coverage includes short/long shifts, selected weekdays, zero search
  budget, weekday-specific opening hours, absent/closed days, zero active staff,
  overlapping 100-person crews, the 60-shift cap and exact feasibility boundaries.
- Strict backend types: **zero errors/warnings**; app import: **OK**.
- Frontend source is unchanged from the prior integrated snapshot (4,479 tests,
  build and lint already passed there).

The complete backend suite passed: **26,178 passed, 1 skipped in 1,135.97 s
(18:55), exit 0**. Its separate completion record remained readable after a
transient executor disconnect. The skipped Grounding DINO integration check needs
the optional capture extra and explicit download opt-in. Tests use synthetic
fixtures and no live model calls.
