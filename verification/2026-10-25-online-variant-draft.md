# Save a complete online variant in one operation

Save as a variant previously created a copy, then sent a second request to save
edited products. If validation or the second request failed, a new store remained
with the original products while the UI reported failure. Retrying could create
another incomplete copy.

The copy request now accepts an optional product draft. Product schema and
category/identity checks complete before the variant is written under the online
transaction. The designer submits products, options, name and note together.
Omitted/null products retain the existing copy behavior, and the control store
is not changed.

- Backend baseline: **9 failed, 2 passed in 3.64 seconds**. Final relevant API
  and project-lifecycle tests: **21 passed in 7.08 seconds**. Cases include price,
  stock, name, sponsored badges, empty catalogs/names, negative prices, duplicate
  product IDs, unknown categories, source preservation and saved readback.
- Frontend baseline: **3 failed, 1 passed** with a failed second save. Final:
  **7 distinct online UI tests passed**, including USD/KRW/JPY draft amounts,
  one-request saving, preserved source values and a retained draft after errors.
- Full-source Pyright: **0 errors, 0 warnings**. TypeScript and changed-file
  ESLint passed with no diagnostics; Vite production build passed in **17.45
  seconds** with existing bundle-size/plugin timing warnings. Test-only typing
  errors in the initial fixture were corrected before these final checks.

No paid model calls or native inference were used. Existing incomplete copies
are not automatically changed or removed.
