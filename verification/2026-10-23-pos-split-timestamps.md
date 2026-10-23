# Separate POS dates and clocks without invented visit dates

Pandas parses `09:00` using the execution date. Consequently, a file whose date and clock were in separate
columns could report every visit on the day it was imported. Explicit Monday/Tuesday records reproduced
Friday visits on the test date, and a time-only file could fabricate a weekday distribution.

Traffic extraction now separates clock-only values from complete timestamps. Recognized POS date/time
columns are combined by row, retaining missing-row positions; a clock without a calendar date is excluded.
Existing complete timestamps win ties in completeness. Birth-date/duration columns are not paired as
visits. Timestamp parsing is shared across complete and combined inputs and preserves local wall clocks.

- Before the fix: **17 failed, 1 passed in 0.96 s**.
- Combined split-time, identifier, timezone and existing traffic checks: **71 passed in 2.23 s**.
- After restricting pairing to recognized date/time labels and adding unrelated-field cases, the split-time
  matrix passed **20 tests in 0.62 s**. The other 53 cases exercise unchanged complete-timestamp paths.
- Final strict Pyright on `application/supplemental.py`: **0 errors, 0 warnings**.
- `git diff --check`: clean.

Cases cover CSV/XLSX, 24-hour and AM/PM strings, native time/date cells, midnight, seconds/fractions,
time-zone clock suffixes, reversed column order, partial invalid records, non-default row indices,
complete-timestamp precedence, and preserving real receipt dates across daily counter resets.
No model calls, frontend rebuild or full-suite rerun was used.

```bash
# From backend/
.venv/bin/pytest -q tests/engine/test_supplemental_split_times.py tests/engine/test_supplemental_pos_parsing.py tests/engine/test_supplemental_visit_identity.py tests/engine/test_calibration_knobs.py::test_traffic_from_pos_export_counts_baskets --tb=short
.venv/bin/pytest -q tests/engine/test_supplemental_split_times.py --tb=short
.venv/bin/pyright src/store_emulator/application/supplemental.py
```

This adds recognized English/Korean POS date/time labels; it does not infer arbitrary columns' meanings.
It is a main-branch fix after v0.4.11 and does not rewrite published binaries or existing generated data.
