# Embedded workbook photo SKU alignment

The product importer and image extractor decoded SKU cells with different
libraries. Formula, hyperlink and rich-text cells became `[object Object]` in the
image path, while products used their cached/displayed values. Headers with
surrounding spaces were accepted for products but rejected for images. Date cells
also decoded differently. An ordinary object used as a photo map additionally
mistook inherited names such as `constructor` for already-extracted SKUs.

Product parsing now supplies its normalized SKU map keyed by original worksheet
row to image extraction. This retains row positions across blank rows and leading
empty rows. SKUs are trimmed consistently with the backend before matching
uploaded image URLs. Extraction uses a Map and returns own record entries, so
prototype-related names are supported. The existing first-image-per-SKU and
nearest-following-SKU behavior for images anchored on empty filler rows remains.
Formula values come from saved workbook results; formulas are not evaluated.

Verification used real ExcelJS-generated workbooks and embedded PNG bytes:

- Baseline: 11 failures and 10 passes in 0.79 seconds.
- 103 related Excel, upload component and image API cases passed in 3.05 seconds.
- Four added cases cover 96 products with different image bytes across leading
  blank rows and row spacings 1, 3 and 7, plus duplicate SKUs and filler anchors.
  All 25 extraction cases passed in 1.09 seconds (107 unique focused cases total).
- The final duplicate-image byte assertion passed independently after replacing
  an unsupported typed-array API in that test.
- TypeScript and ESLint passed. Production Vite build passed in 17.25 seconds;
  existing chunk/plugin timing warnings remain.

No live model calls or backend changes were needed.
