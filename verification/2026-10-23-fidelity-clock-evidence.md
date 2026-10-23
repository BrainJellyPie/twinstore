# Use actual clock evidence for POS hourly comparisons

Date-only timestamp strings and native Excel date cells previously became hour zero. Fidelity then
scored those receipts as midnight visits even though the input contained no visit time. Conversely,
a receipt whose first line lacked a clock lost valid times on later lines; swapping product-line order
could remove or change its hourly score.

Require explicit clock text (including midnight, AM/PM and validated HHMM), preserve native Excel types
long enough to distinguish date-only/midnight cells, and use each receipt's earliest available hour once.
Receipts without any clock remain available for basket/product metrics but not hourly comparisons.

Focused evidence:

- CSV/XLSX date formats and empty values; explicit midnight, local UTC offsets, AM/PM and HHMM clocks;
  native Excel date/datetime/time cells; explicit hour overrides; partial and reordered receipt clocks.
- Before the fix: **16 failed, 30 passed in 1.09s**.
- New cases plus receipt-scope, POS validation and analysis modules: **135 passed in 0.97s**.
- Strict Pyright on the two changed modules: **0 errors**.

Native Excel midnight datetimes are ambiguous with date-only cells; explicit text such as `00:00` or
an `hour` column disambiguates true midnight visits. Existing reports are not rewritten. No live model
calls, full suite, frontend or release binary changes.
