# POS array-formula cached values

An XLSX array formula can put `<f>` only on its anchor and declare a multi-cell
result range. With a cached anchor but no cached child, the earlier formula
check saw no formula on the child. Direct probes dropped the second SKU row,
defaulted its quantity to 1, or defaulted its price to 0.

The streaming workbook scan now records array ranges when POS requests cell
validation. Bound their total area and encompassing worksheet rectangle before
allocation. Only sheets with multi-cell arrays need a second streaming pass;
that pass records cached positions in a byte-per-cell bitmap, at most 2 MB under
the existing two-million-cell limit. It handles absent cells and cells appearing
before anchors. Collect the first missing result in each affected column, so
POS still checks only the sheet and columns it imports. Invalid array references
flag their anchor; oversized ranges fail before pandas loads the table.

Cached numeric/text results, zero and explicit empty text remain valid. Missing
array results in unused notes do not block POS data. This does not evaluate
formulas or establish cache freshness, and adds no binary-XLS support.

The initial 21-case matrix had 14 failures and seven passing controls. Expanded
cases include two-dimensional arrays, malformed references, absent cells and
trailing ranges. 166 focused formula, duplicate-column, API and workbook-budget
checks passed in 5.29 seconds; Pyright reports zero errors after typing the
streaming parser's element stack. API tests retain prior fidelity JSON byte for
byte on rejection. No frontend build, full suite or paid model calls.
