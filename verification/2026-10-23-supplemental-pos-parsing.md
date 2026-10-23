# Supplemental POS identifier and timezone parsing

Pandas numeric/null inference changed receipt and register identifiers before traffic extraction.
Distinct IDs such as `01` and `1` collapsed, long numeric strings could lose precision when blanks were
present, and literal `NA`/`NULL` identifiers disappeared. Timestamp arrays with different UTC offsets
or mixed aware/naive values also raised an exception, disabling the entire fitted traffic profile.

Traffic extraction now loads frames without numeric/null inference for identifiers, while the separate
supplemental statistics pipeline retains its existing numeric inference. Mixed-timezone timestamps fall
back to per-row parsing and retain their recorded wall clocks before fitting local weekdays/hours.
Date-only Excel cells remain without a visit time; converting their dtype to object must not invent
an explicit midnight.

- Before the fix: **17 failed, 4 passed in 1.02 s**.
- Final focused validation: **53 passed in 2.12 s**, including CSV/XLSX imports, leading zeros in receipt
  and register IDs, literal null-like IDs, missing/large identifiers, offset/DST boundaries, mixed naive/
  aware values, date-only cells, numeric-summary compatibility and the preceding receipt-identity cases.
- Strict Pyright on `application/supplemental.py`: **0 errors, 0 warnings**.
- `git diff --check`: clean. No model calls, full suite or frontend rerun.

The initial implementation passed its behavior checks but exposed pandas typing errors; the final
typing adjustment was followed by the focused checks above.

```bash
# From backend/
.venv/bin/pytest -q tests/engine/test_supplemental_pos_parsing.py tests/engine/test_supplemental_visit_identity.py tests/engine/test_calibration_knobs.py::test_traffic_from_pos_export_counts_baskets --tb=short
.venv/bin/pyright src/store_emulator/application/supplemental.py
```

The time-zone policy uses each exported local clock; it cannot infer that an export should instead
be converted to an unstated store timezone. A separate discovery remains open: time-only columns can
borrow the execution date, and separate date/time columns need to be combined explicitly.

This is a main-branch fix after v0.4.11. Published binaries and previously generated customers are unchanged.
