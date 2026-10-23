# Bound POS CSV expansion before allocation

POS uploads had a 50 MB byte limit but no limit on the rectangular table allocated by pandas.
A header with 2,000 columns and 1,001 short data rows fits below 50,000 bytes yet requires
over two million cells. Wider or longer variants could exhaust memory while scoring sales.

Customer and POS CSV imports now share the streaming structure/cell-budget scan. POS retains
its comma separator and UTF-8/BOM/CP949 decoding policy, with a two-million-cell limit matching
customer imports. Surplus fields, malformed quoting and empty inputs fail before pandas.
Quoted multiline values count as one cell, and long notes remain supported within upload limits.
No records are silently truncated. Existing customer exception imports and HTTP status mapping
remain compatible through aliases to the shared CSV errors.

Focused offline evidence:

- Before repair: **14 failed, 5 passed in 1.35s**. Mocked pandas readers demonstrate that unsafe
  sparse and invalid tables reached allocation; no oversized dataframe was actually allocated.
- CSV encoding/newline combinations, exact budgets, header-only width, blank lines, quoted
  multiline/long notes, customer preflight, workbook bounds, POS numeric/calendar/receipt
  semantics and fidelity regressions: **894 passed in 8.15s**.
- Strict Pyright on the three changed application modules: **0 errors**.

No full suite, live model calls, frontend or release changes.
