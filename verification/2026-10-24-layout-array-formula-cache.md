# Layout workbook array-formula caches

An XLSX array formula can declare a range while omitting one or more result
cells from the file. SheetJS retains the anchor but does not synthesize missing
children. Importing those cells previously cleared SKUs, defaulted prices to
zero or lost product rows. Eight of the initial 17 cases reproduced missing
validation, including a declared range exceeding the cell budget.

The parser now validates and deduplicates declared array ranges, includes them
in the actual sheet bounds, and checks their saved values before importing.
Both the sheet rectangle and total distinct array areas are capped at two
million cells. Missing values are retained only once per column. Existing
localized cell-value errors identify the affected spreadsheet coordinate.
Cached numeric zero and explicit empty strings retain their existing meaning;
missing results in unused notes do not prevent import.

Validation:

- 263 existing workbook tests passed; the final 27 array cases passed.
- Missing children in five imported columns, cached controls, zero/empty
  results, unused notes, absent tails, two-dimensional arrays, error/stub cells,
  header formulas, malformed ranges, oversized ranges and shifted absolute
  references are covered with real XLSX serialization.
- ExcelJS supplies malformed/absolute references because the SheetJS writer
  silently removes some of that metadata. No mocked parser is used.
- TypeScript and changed-file ESLint passed. Vite built in 16.99 seconds with
  the existing large-chunk and Babel timing warnings.

This validates stored results; it neither recalculates formulas nor detects
stale but present cached values.
