# Validate track tables before measuring movement

DictReader silently retained surplus fields under a discarded key. An unquoted timestamp such
as `1,250` therefore became `1`, and extra coordinate fields could shift later measurements.
Unterminated quoted values were also accepted. Many unused header columns with short data rows
caused repeated large padded dictionaries despite the small upload size.

Track imports now use the shared CSV structural scan before point parsing, with a two-million-cell
budget including missing fields. Existing byte/sample limits remain. The reader handles LF,
CRLF and CR consistently, including quoted multiline and long auxiliary notes; missing optional
trailing columns remain allowed. Invalid files produce a 400 response without replacing prior reports.

Focused offline evidence:

- Extra numeric/empty fields, unterminated quotes, sparse records, newline variants, quoted notes
  and HTTP report preservation: **14 failed, 4 passed in 3.30s** before repair. Long-note test IDs
  were shortened afterward to avoid oversized failure output; assertions were unchanged.
- New structural/resource/API checks and existing movement regressions: **39 passed in 3.91s**.
- Changed movement application module strict Pyright: **0 errors**.

The sparse fixture is below 40 KB and reaches the table limit before TrackPoint parsing (mocked).
No full suite, real movement data, model calls, frontend or release changes.
