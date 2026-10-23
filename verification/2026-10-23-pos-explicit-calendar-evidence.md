# Recognize explicit calendar and clock evidence across POS formats

Receipt scoping recognized only a few numeric date shapes. `10/22/26 12:30`, `22 Oct 2026 12:30`
and `20261022T123000` were left without dates; the same receipt number on two days became one
basket. Compact clocks also lost the hour. Standard hyphenated four-digit dates worked, hiding
the defect in common fixtures.

Parse each unique timestamp with two distinct default dates/hours and retain only calendar dates
or hours that agree. This recognizes complete input without inventing missing components. Leap-year
defaults with 31-day months keep partial February 29 and day 31 valid during this evidence check.
The existing 4,096-entry per-import cache, local clock interpretation, HHMM convention and special
treatment of native Excel midnight/date-only cells remain.

Declare the parser dependency directly and lock python-dateutil 3.0.0 (latest stable confirmed on
PyPI on 2026-10-23). Other locked package versions do not change; dateutil now also depends on the
already locked tzdata. Release binaries are unchanged.

Focused evidence:

- 130 new checks: nine full timestamp formats × CSV/XLSX × timestamp/date columns × midnight/noon;
  partial calendar/time fields, malformed/huge inputs, all twelve named months and several dates.
- Corrected before-fix baseline: **106 failed, 24 passed in 1.17s**.
- Initial combined run: 437 existing POS/fidelity/clock/cache checks passed; two new assertions wrongly
  treated `2026` as a year despite the established HHMM convention (20:26). Replaced that ambiguous
  partial-date fixture with `2026-10`; the corrected 130 new checks **passed in 1.00s**.
- Existing supplemental CSV/POS parsing with the updated dependency: **21 passed in 1.61s**.
- Strict Pyright on the changed module: **0 errors**. Backend application import: **OK**.

Two-digit ambiguous dates retain the parser's existing month/day interpretation; this change does
not infer a locale or convert time zones. No live model requests, full suite or frontend changes.
