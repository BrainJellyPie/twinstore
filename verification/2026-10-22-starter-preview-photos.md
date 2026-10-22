# Photos in starter-product previews

Starter placement previews now resolve the current uploaded, reviewed or bundled photo for reused
products, including catalog SKUs saved before a photo was added. This changes only the preview response:
source files and the values copied into the child layout remain unchanged. Reviewed immutable photos
retain priority over current uploads; explicit and bundled references retain their established order.
Products with neither an image nor a display name show their SKU in the VLM grid.

Added 32 prepared-food, pharmacy and personal-care photos. The catalog now contains 1,208 products in
107 categories and 224 bundled photos. Merged the completed library-photo localization branch through
94e291e and the dwell-map correction through 7a49d43.

Validation on 2026-10-22:

- Targeted image, old-SKU and starter API checks: 1,037 passed. Includes three currencies, absent/custom/
  reviewed image references, uploaded-photo precedence, unchanged source bytes, original child values,
  visible fallback SKU labels, and photo/number identity across the catalog.
- Strict backend types: zero errors; application boot passed.
- Full backend: 18,686 passed, one skipped in 733.96 seconds.
- Full frontend: 4,022 passed in 229 files; build passed; lint retained 19 warnings and zero errors.
- Browser: automatic selection remained the new-store default. Real create, shelf-grid and placement
  preview APIs showed the new photos, including a reused SKU whose stored photo URL was absent.
  Subsequent reads and previews preserved source bytes. All 32 new photo crops, the numbered VLM grid
  and the reuse preview were visually inspected. Realistic rendering loaded ten images without errors.
- Wheel includes all fourteen original atlases; product/category/photo totals checked directly.

Browser product selection and personas used controlled replies. No live provider completion or paid
simulation was invoked.
