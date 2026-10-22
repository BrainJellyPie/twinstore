# New photos for previously saved starter products

Previously saved starter products with no photo URL now use the current bundled photo for their exact
catalog SKU. This works in layout responses and the VLM grid, including projects that have never uploaded
a photo. Uploaded and explicit photos keep their existing priority. Product names, prices, SKU identities
and saved layout bytes do not change when the layout is read. Unrelated products never match by name.

Added 32 kitchen, pet, technology, household and personal-care photos. Totals remain 1,208 products and
107 categories, with 192 bundled photos. Merged main through `19919b7` (0.4.5 and technical-report updates).

Validation on 2026-10-22:

- Final legacy-photo and read-only image checks: 604 passed, covering every photographed product in
  three currencies, renamed products, modified prices, unknown same-name SKUs, upload precedence,
  reviewed immutable photos, actual layout/preview responses and unchanged stored JSON.
- Strict backend types: zero errors; application boot passed.
- Full backend: 18,494 passed, one skipped in 650.84 seconds.
- Full frontend: 4,001 passed in 228 files; build passed; lint retained 19 warnings and zero errors.
- Browser: a real created layout was changed in the disposable fixture to remove all stored photo URLs.
  Layout and shelf-preview APIs still returned the new photos, and subsequent reads left its bytes
  unchanged. Both new galleries and the actual VLM grid were visually inspected. Realistic rendering
  loaded 30 images successfully without page errors. Product selection/personas used controlled replies.
- Wheel includes all twelve original atlases; product/category/photo totals checked directly.

No live provider completion or paid simulation was invoked.
