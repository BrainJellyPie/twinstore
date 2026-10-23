# Avoid repeated date parsing while importing POS receipts

Profiling 4,000 product lines with one timestamp found **8,000 pandas date-parser calls**: the same text
was parsed for receipt date scope and again for the hour on every row. This took **1.634s** locally.

Use one import-local date parser with at most 4,096 recent cached strings. Receipt grouping and hourly
extraction share its results, including invalid dates. No values are retained across imports.
The same 4,000-row reproduction then needed **1 parse and 0.041s**. This measurement is specific to a
repeated-timestamp input, not a general speed guarantee; distinct timestamps still require parsing.

Focused evidence:

- CSV and Excel with 2,000 rows each, repeated local UTC offsets, date-only values, invalid dates and
  AM/PM times. Assert unchanged clock/scope values and bounded parsing work for the fixed set of strings.
- Before the fix: **2 failed in 2.36s**.
- New cases plus clock-evidence, receipt-scope, POS validation and analysis modules:
  **137 passed in 1.18s**.
- Strict Pyright on the changed module: **0 errors**.

No live model calls, full suite, frontend or release binary changes.
