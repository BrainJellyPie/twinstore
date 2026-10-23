# Supplemental CSV export formats

## Problem and change

A 250-visit Korean CSV produced a traffic profile in UTF-8 but no frames or profile in CP949 or
UTF-16. Semicolon and tab exports became one column, losing their timestamp/receipt structure.
The loader retried UTF-8 failures as UTF-8-with-BOM, which cannot decode these exports.

Decode Unicode BOMs explicitly (UTF-32 before UTF-16), otherwise try UTF-8-with-BOM and the
existing POS importer's CP949 fallback. Detect comma, semicolon or tab from a bounded sample;
ambiguous input retains the comma default. Parse failures still return no frames. Workbook
handling, summary numeric inference and traffic identifier preservation are unchanged.

## Focused evidence

- New matrix crosses seven encodings, three delimiters and LF/CRLF, with quoted delimiters,
  multiline Korean cells, duplicate product lines and distinct leading-zero receipt IDs.
- Additional cases cover one-column notes, decimal commas, empty/malformed CSVs, invalid
  BOM payloads, an invalid workbook and unsupported extensions.
- Before the change: **39 failed, 14 passed in 0.59s**. An initial test assertion compared
  normalized floating-point shares exactly; corrected it to an approximate comparison before
  recording this baseline (that earlier run was 43 failed, 10 passed).
- New tests plus the three POS timestamp/identity modules: **125 passed in 2.85s**.
- Strict Pyright on `application/supplemental.py`: **0 errors**.

No live model calls, full suite, frontend changes or release binary changes. This supports the
listed encodings and separators; it is not arbitrary charset detection, and decimal-comma
amounts remain text rather than assuming a financial locale.
