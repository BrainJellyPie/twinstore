# POS visit identities and timestamp boundaries

Supplemental CSV/XLSX traffic extraction selected the first column containing words such as `order` or
`transaction` as a basket ID. An `order_time` column before `order_id` collapsed separate orders at the
same timestamp. Deduplicating receipt IDs across the whole file also discarded later days or registers
whose counters restarted. Explicit midnight timestamps were rejected as if they were date-only values.

Receipt columns now match normalized ID names rather than arbitrary substrings. Visits are deduplicated
by calendar date, receipt ID and available store/register identifiers. Rows without a receipt column
retain the existing one-row/one-visit behavior. Explicit time strings allow midnight-only traffic;
date-only, numeric and unreadable values still do not fabricate a time-of-day distribution.

- Initial boundary matrix: **28 failed, 3 passed in 0.84 s**.
- Fixed matrix plus the existing POS traffic calibration regression: **32 passed in 1.08 s**.
- Strict Pyright on `application/supplemental.py`: **0 errors, 0 warnings**.
- `git diff --check`: clean.

Tests permute timestamp/ID/other column ordering, use English and Korean ID labels, repeated dates and
register/store identifiers, and midnight/date-only values. Generated CSV and XLSX exports contain 350
visits across seven days and two terminals with shuffled multi-item receipt rows; exact weekday/hour
counts must survive extraction. No live model calls or full-suite/frontend reruns were used.

```bash
# From backend/
.venv/bin/pytest -q tests/engine/test_supplemental_visit_identity.py tests/engine/test_calibration_knobs.py::test_traffic_from_pos_export_counts_baskets --tb=short
.venv/bin/pyright src/store_emulator/application/supplemental.py
```

Separate exploratory assortment generation used seed 1041126 for 80 combinations of formats, USD/KRW/JPY,
8–40 by 6–40 floors, eight layout styles, density, aisle width, shelf direction and checkout counts.
71 generated floors selected products successfully; nine rejected checkout configurations that did not
fit. No further issue was found in that sweep (3.38 s). The script/report remain in workspace scratch.

Execution connectivity briefly failed after the checks; it recovered with the edits intact before commit.
This is a main-branch fix after v0.4.11; published binaries are unchanged. It changes future traffic
extraction and does not rewrite previously generated customer data.
