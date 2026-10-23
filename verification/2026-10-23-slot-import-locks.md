# Excel product imports share the layout save lock

Slot imports read and rewrote an entire setup without the file lock used by
editor and operations saves. If an editor save paused before writing, a
completed import could be overwritten with the old products. In the opposite
order, the import could overwrite a newer name, memo or operations configuration.

The complete import read/validate/write operation now holds the same per-layout
file lock. It reads fresh state after acquiring the lock and returns 503 on
contention timeout. Other layouts remain independent. Import validation and
product placement rules are unchanged.

Focused offline verification:

- Before the fix: **7 failed / 1 passed**, 3.43 seconds.
- Import races, price validation, atomic floor saves, simulation transitions
  and layout deletion: **51 passed**, 11.99 seconds.
- Eight new cases cover both write orders with name/memo/operations saves,
  same-layout API contention with unchanged original file bytes, and unrelated
  layout locks.
- Strict backend types: **zero errors/warnings**. API checks import the app.

Frontend source is unchanged from the atomic-floor-save revision, verified by
30 editor tests, TypeScript and its production build. Full suites were not
repeated under the user's focused-validation policy.
