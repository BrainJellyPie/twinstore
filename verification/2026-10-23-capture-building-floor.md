# Shelf capture layouts stay on their source floor

Individual, multi-photo and combined-shelf applications created child layouts
without the source's building metadata. A captured layout from a basement or
upper floor therefore lost its building ID, floor level, label and floor count.
Other editing workflows already preserved these fields.

Both capture save paths now copy validated building metadata from the source.
Standalone layouts remain standalone, and saved operations/source data remain
unchanged.

Focused offline verification:

- Reproduction matrix: **12 failed / 6 passed**, 4.28 seconds.
- Capture-batch, currency and correction regressions: **54 passed**, 5.58 seconds.
- The expanded API matrix covers individual/multiple/combined photos, basement
  and upper floors, standalone sources, and configured/unconfigured operations.
- Strict backend types: **zero errors/warnings**.

No live models or real project data were used. Frontend source is unchanged;
full suites were not repeated under the user's focused-validation policy.
