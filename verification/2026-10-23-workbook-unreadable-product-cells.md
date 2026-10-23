# Product workbook cell errors and missing locations

## Reproduced failures

SheetJS converts Excel error cells such as `#REF!` to the configured empty
default when producing JSON rows. It also drops formulas without a saved result
unless stub cells are requested. The importer consequently treated an erroneous
SKU as a deleted placement and an erroneous price as zero. A missing rack ID
silently removed a product row from the replacement payload. Blank spacer
headers also exposed a sparse-array iteration error in the preceding duplicate
column validation change.

The initial focused regression module had 112 failures and 3 passing controls
in 1.33 seconds. Direct workbook round-trips also confirmed that modern error
strings (`#SPILL!`, `#CALC!`, `#BLOCKED!`, `#UNKNOWN!`) have error cell type but no
numeric code in this SheetJS version; these require checking the type even when
the numeric value is absent.

## Change

- Retain uncached formula stubs during workbook decoding. Include formula/error
  cells in the populated bounds, but continue ignoring ordinary blank stubs.
- Reject unreadable header cells and unreadable cells in imported product
  columns before JSON conversion. Identify the original worksheet address and
  explain how to fix/recalculate/save the file in all six interface languages.
- Preserve cached values, including numeric zero and deliberately empty text.
  Errors in unrelated notes columns remain ignored.
- Reject a nonempty SKU with an absent/blank/whitespace rack ID. Report the
  original row; trim valid rack IDs consistently with the backend.
- Normalize sparse header positions without throwing on unused spacer columns.

All rejection occurs before image extraction/uploads or slot replacement.
This does not recalculate formulas or verify that a saved cached result is fresh;
spreadsheet software must calculate and save the workbook before import.

## Verification

- 335 related workbook, image association, upload lifecycle and catalog checks
  passed in 6.61 seconds after the initial changes.
- Twelve added modern-error cases cover SKU, price and optional header cells.
  The final focused cell module passed all 128 cases in 1.69 seconds (347 unique
  checks across the two successful runs).
- Coverage includes all eleven imported fields with eight standard error codes,
  uncached formulas, shifted headers/original addresses, missing rack variants,
  separate notes columns, cached zero/empty results and spacer headers.
- UI checks cover all six languages, switching language after rejection, no
  image or product mutation on failure, and a subsequent successful upload.
- TypeScript and changed-file ESLint passed after removing two unnecessary
  escapes in a test formula. Production build passed in 16.39 seconds; existing
  large-chunk and Babel plugin timing warnings remain.
- No live model calls or backend test-suite run.
