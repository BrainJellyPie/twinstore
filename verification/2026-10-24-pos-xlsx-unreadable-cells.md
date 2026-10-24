# POS XLSX error cells and uncached formulas

## Reproduction

An XLSX containing `=1+1` without a saved result in a quantity or unit-price cell
was read as blank by pandas/openpyxl. The parser then supplied quantity 1 or
price 0. A missing cached SKU result caused that entire receipt line to be
skipped while other rows still imported successfully. Error cells in identifiers,
timestamps and scope fields could similarly turn into misleading text or missing
evidence. Some numeric error cells were already rejected, but lacked worksheet
coordinates and recovery guidance.

The initial regression run had 27 failures and 9 passing controls in 0.88
seconds. These include missing cached values and the diagnostic expectations
for error cells, not 27 separate previously accepted data-loss scenarios.

## Change

The existing streaming XLSX budget scan optionally collects error/uncached
formula coordinates while it bounds archive expansion and actual worksheet
ranges. It continues releasing parsed elements as it goes. POS imports select
issues from the actual first worksheet part used by openpyxl's read-only reader,
rather than assuming a filename or ZIP-entry order.

Reject unreadable header cells and cells in selected data/scope columns with
their original one-based row/column and instructions to fix, recalculate and
save. Unknown notes, lower-priority unused aliases and other worksheets do not
block the import. Saved formula values remain supported, including zero and
explicitly empty text; a deliberately empty cached SKU still means an unused row.

This checks XLSX cell types and saved results. It does not evaluate formulas,
verify cache freshness, or add equivalent formula inspection for legacy binary
XLS files. Workbook budgets remain unchanged. The worksheet-part lookup uses
openpyxl 3.x's read-only worksheet path under the existing `<4` dependency bound;
if a reader cannot identify a worksheet with reported issues, the import fails
explicitly rather than silently skipping the check.

## Verification

- 184 focused formula/duplicate-column/ordinary-POS/workbook-budget checks passed
  in 4.12 seconds after the initial implementation.
- 219 follow-up checks passed in 4.93 seconds, covering newer Excel error codes,
  formulas beyond the last cached visible row, renamed worksheet parts, cached
  values, unrelated notes/sheets, lower-priority aliases and calendar/receipt data.
- Three API checks verify HTTP 400 before analysis for SKU/quantity/price formulas
  without cached results, retaining existing fidelity JSON byte for byte.
- Resource tests intercept both pandas Excel entry points and still reject
  oversized archives/sparse rectangles before loading a dataframe.
- Both changed modules pass Pyright after narrowing pandas' multi-sheet return
  annotation for the explicitly selected first worksheet. No new `Any` types.
- No full suite, frontend rebuild or paid model calls.
