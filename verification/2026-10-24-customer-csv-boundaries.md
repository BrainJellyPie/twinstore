# Keep customer CSV columns aligned and table allocation bounded

Pandas can interpret surplus CSV fields as an implicit index and move the remaining values under
different named columns. For example, a receipt value `0900` became the `timestamp` column while
the actual timestamp disappeared into the index. That corrupted the evidence presented to the
customer-summary pipeline. Separately, a wide header followed by short rows padded a small upload
into a much larger rectangular table.

A shared customer-CSV preflight decodes the already supported encodings, determines the separator,
checks CSV quoting and record widths, and bounds header width times row count to two million cells
before dataframe loading. Short rows remain supported within the budget; surplus fields are rejected.
The header supplies separator detection when inconsistent rows defeat whole-sample detection, so
malformed semicolon/tab files cannot become apparent one-column notes. A dataframe index guard
also prevents implicit index inference from becoming customer evidence.

New-store creation runs the same preflight before saving a project, selecting products or starting
persona generation: structural errors return 400 and allocation limits return 413. Existing file
reloads keep their empty-result failure contract. Valid quoted multiline notes and long text retain
their values; identifiers and numeric inference retain the existing two reading modes.

Focused offline evidence:

- **41 failures in 3.78s** before repair: UTF-8 BOM/Korean Excel/UTF-16/UTF-32, comma/semicolon/tab,
  surplus leading/trailing/empty fields, broken quoting, API side effects and sparse allocation.
- Related customer parsing, visit identities, split timestamps, workbook bounds and project-template
  checks: **206 passed in 12.19s**. Strict Pyright on all three changed modules: **0 errors**.
- Additional exact-budget, missing-cell, leading-blank, multiline and 200,000-character-note cases:
  final focused CSV checks **47 passed in 3.12s**.

The sparse test uses a file below 30 KB with a 2000-column header and 1001 short rows. A mocked
dataframe reader confirms rejection happens before allocation; no memory-exhaustion attempt was run.
No live model calls, full suite, frontend or release changes. The new CSV limit applies to customer
supplemental data, not the separate 50 MB POS CSV endpoint.
