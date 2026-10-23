# Bound spreadsheet expansion before dataframe allocation

A valid 4,873-byte XLSX with a header, one receipt and a cell at row 50,000 / column 2,000 made pandas
materialize a 100-million-cell rectangle. In a separate process restricted to its existing address
space plus 256 MiB, the read raised `MemoryError` in 0.392s (315.1 MiB peak RSS). No unbounded read
was attempted. The normal 10 MB upload limit did not protect this path.

Before pandas, check the ZIP's declared expanded size (100 MiB maximum) and stream worksheet XML
to bound the sum of actual row/column rectangles (2,000,000 cells, including empty gaps). Ignore
potentially incorrect `<dimension>` hints. The stream releases parsed elements, recognizes sheets
regardless of part filenames, and does not let unrelated malformed XML bypass later sheets.

The wizard performs this check before layout preparation, model calls, project writes or generation.
Over-budget uploads return HTTP 413 with recovery guidance. Both supplemental readers and Excel POS
imports also check before dataframe loading. No sampling or truncation changes visit counts.

Focused evidence:

- **170 passed in 7.29s**: new resource-boundary tests plus existing project wizard, CSV-format,
  supplemental POS and POS validation cases.
- New cases cover sparse ranges, absent/false dimensions, nonstandard worksheet part names, malformed
  unrelated XML, archive expansion, exact grid-budget boundaries, multi-sheet totals, implicit cell
  columns, upper-case extensions and rejection before project/generation mutation.
- Ordinary files retain all rows and leading-zero IDs. Dataframe spies confirm oversized files never
  reach pandas. The original sparse fixture is rejected by preflight in about 0.0015s locally.
- Strict Pyright on all four changed application modules: **0 errors**.

No full suite, live model calls, new dependencies, frontend or release asset changes. These are
ingestion budgets, not a process-wide memory guarantee. Legacy non-ZIP `.xls` parsing and CSV limits
are unchanged. Existing malformed supplemental-file fallback behavior remains unchanged.
