# Reimport product workbooks with valid shelf coordinates

Workbook export emitted product rows for dining tables and empty rows for locked
faces. The slot API correctly rejected those rows, so unchanged downloaded files
could not be imported. Export and import also hardcoded block zero, omitting the
other blocks of legacy racks; the grid editor's legacy dialog does not guard the
separate workbook controls.

Exports now include only shelves, fridges and counters, enumerate their rotated
blocks, and omit internal faces. A `block` column preserves the full coordinate.
Blocked faces remain visibly marked in the workbook, but empty marked rows are
excluded from upload. A user-entered SKU on a marked row still reaches normal
server validation. Old workbooks without `block` retain their one-cell meaning.

## Verification

- Reproduced HTTP 400 for exported table rows and empty locked-face rows.
- Initial workbook regressions: all 7 tests failed.
- 44 permanent workbook tests plus an export probe passed in 1.50 seconds.
  Coverage includes all four rotations, non-product fixtures, multiple blocks,
  exposed/internal faces, old headers, blocked markers and invalid block indexes.
- Cross-language round trips: backend-generated urban convenience, café/bakery
  and specialty café layouts plus L-shaped racks at 0/90/180/270 degrees were
  exported and parsed by the frontend, then reimported through the real slot API.
  All seven requests succeeded and preserved all 1,036 product placements,
  coordinates, names, current/reference prices and promotion labels; none were
  cleared as unreachable. The temporary export probe was removed after the check.
- TypeScript and targeted ESLint pass. Production build succeeds in 16.79 seconds
  with existing bundle-size and Babel timing warnings. No model calls.

Previously downloaded files that omitted rack blocks cannot recover that lost
information; download a fresh workbook from the saved layout.
