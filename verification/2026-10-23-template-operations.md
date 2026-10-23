# Template alternatives retain their source operating settings

Reusing generation settings created a linked child layout with its building
metadata but dropped saved operations. Running that alternative with its saved
defaults silently disabled shared stock, crew and queues. Reusing whole
buildings had the same problem on every floor.

Template preparation now copies operations from its source snapshot. Each
reordered or duplicated floor inherits its own source's settings. New layouts
without a source and sources with operations disabled remain unconfigured.
Subsequent edits to a child do not change the source or a sibling.

Focused offline verification:

- Before the fix: **2 failed / 2 passed**, 3.73 seconds. Both configured reuse
  paths lost their settings; unconfigured controls passed.
- After the fix: **12 passed**, 4.68 seconds, covering template/building reuse,
  weekday crew shifts, finite stock, disabled delivery, independent floor
  settings, explicit run-time opt-out, source preservation, invalid sources and
  building write rollback.
- Strict backend types: **zero errors/warnings**.

No live models or real project data were used. Frontend source is unchanged;
full suites were not repeated under the user's focused-validation policy.
