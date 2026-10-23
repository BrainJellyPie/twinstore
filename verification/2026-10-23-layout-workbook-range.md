# Product workbook worksheet ranges

## Reproduction

A 5,673-byte XLSX with four headers and one product declares
`A1:XFD1048576` as its worksheet dimension. The previous header conversion
scanned that entire rectangle synchronously on the browser thread. An isolated
Node reproduction exceeded a two-second process timeout before returning the
header. It was terminated, not left running. No live model calls were used.

The three small XLSX fixtures in
`frontend/src/features/layouts/excel/__tests__/fixtures/` contain `rack_layout`
headers `rack_id, face, level, sku` and the row `rack, North, 1, tea`.
They were generated with SheetJS, then edited with Python's `zipfile`:

- `inflated-dimension.xlsx`: worksheet dimension `A1:XFD1048576`.
- `understated-dimension.xlsx`: dimension `A1:D1`, with the product still in row 2.
- `distant-product.xlsx`: dimension `A1:D1048576`, with another actual product
  (`far-tea`) in the final row.

## Change

Compute the populated cell bounds before converting to rows. Empty/stub cells
do not expand that range. Read only the first actual row for the header check.
Retain original worksheet coordinates so SKU image associations remain correct.
Include real cells outside an understated dimension instead of dropping them.

Reject an actual bounding rectangle above 2,000,000 cells before image uploads
or slot replacement. This accommodates 50,000 placements with every supported
template column. Distant actual values are rejected together with the workbook;
products are never truncated to satisfy this limit. The recovery message follows
the selected language, including a language change after an error.

This bounds worksheet-to-table conversion, not ZIP decompression or the initial
SheetJS workbook read. It does not claim protection against arbitrary compressed
archive expansion. Very sparse real data can exceed the rectangle limit and
must be moved closer together before import.

## Verification

- 151 focused Vitest checks passed in 9.49 seconds across workbook import/export,
  image extraction, upload lifecycle and translation catalogs.
- New cases cover inflated/understated dimensions, distant actual products,
  shifted headers, blank rows, original image row numbers, empty/missing headers,
  50,000 placements and all six error-message languages with a successful retry.
- TypeScript and changed-file ESLint passed. A test's `Array.at` was replaced by
  indexing to match the project's configured standard-library target.
- Production Vite build passed in 16.36 seconds; existing large-chunk and Babel
  plugin timing warnings remain.
- No backend changes, paid model calls or full backend test run.
