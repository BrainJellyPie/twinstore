# Ambiguous product workbook columns

## Failure and change

A workbook with `sku` and `SKU` headers and values `tea` and an empty string
previously imported an empty SKU. Key normalization overwrote the first column.
The slot replacement contract treats an empty SKU as an empty placement, so a
second, unused column could clear existing products. Exact duplicate headers
instead received SheetJS suffixes, silently selecting the first value. Price
aliases also had implicit priority independent of the visible column order.

Validate the original header before SheetJS converts product rows. A supported
field may appear only once after case/space normalization and price-alias
resolution. Reject the whole import before image writes or slot replacement.
Explain the ambiguous field in all six languages. Single legacy price aliases,
zero prices and numeric zero SKUs remain supported. Repeated unknown notes
columns remain ignored.

## Verification

- Before the fix, 46 regression cases failed and 4 valid-workbook controls passed
  in 1.11 seconds. These cover every imported field with exact/case/space
  duplicates, both orders of every competing price/reference-price alias pair,
  and ambiguous headers in an otherwise empty workbook.
- After the fix, 173 focused checks passed in 4.45 seconds across column, price,
  coordinate, integrity, image-reference, upload lifecycle and catalog tests.
- Upload tests verify no image extraction, image upload or slot mutation after
  rejection, language changes while the error is visible, and successful retries.
- TypeScript and changed-file ESLint passed. Production build passed in 16.43
  seconds with existing large-chunk and Babel plugin timing warnings.
- No backend changes, paid model calls or full backend test run.
