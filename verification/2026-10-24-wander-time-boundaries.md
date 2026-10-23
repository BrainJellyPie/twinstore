# Apply the declared area-navigation time budget

This records the initial route-level repair. The later
[scenario-order follow-up](2026-10-24-action-dwell-scenarios.md) moves normalization to raw action
validation so scenario scaling happens after the bound and is preserved.

The intent prompt already specified at most 120 seconds of dwell per action. Area navigation
used the raw integer before any rack dwell limits, however: huge positive/negative integers could
overflow float conversion, and ordinary out-of-range integers created hours or days of wandering.
Those elapsed times also flow into visit metrics and shared-store operating windows.

Route sanitization now copies area actions with dwell bounded to 0–120 seconds before path
construction. The same sanitized action reaches timeline generation. This covers absent area
bounds and conflicting action labels, since area pathfinding uses dwell regardless of the label.
Original model actions are not mutated, and point-action/rack timing is unchanged.

Focused offline evidence:

- Before repair: **52 failed, 68 passed in 0.98s**, varying negative/zero/boundary/large durations,
  huge integers, missing/single-tile/reversed/outside/huge areas and cardinal/diagonal walking.
- Repaired results exactly match visits supplied with the bounded duration, including paths,
  seeded pauses, midnight-crossing clocks and exit; original decisions remain unchanged.
- Those boundaries plus conflicting labels, wander continuity, offline model-action handling,
  timeline and shared-store regressions: **746 passed in 6.24s**.
- Route-builder strict Pyright: **0 errors**.

No full suite, live providers, long-running operational replay, frontend or release changes.
