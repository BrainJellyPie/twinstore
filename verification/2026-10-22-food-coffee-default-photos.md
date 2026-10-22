# Food and coffee photos in default maps

Added 64 local photos, bringing the catalog to 896 pictures for 1,496 entries in
131 categories. Dairy, prepared meals, desserts, breakfast spreads, home coffee
and tea, baking ingredients, frozen meals, fresh seafood and barista tools now
have a photo for every existing item. Their matching default maps inherit the
photos without changing product names, prices or SKU identities.

Reviewed the latest main branch (10658549). Its completed layout and localization
work was already integrated. Included its remaining model-recovery improvement:
customer-generation failures show one settings action while retaining the
explicit local-model download/start control. Also retained upstream ignore rules
for dependency-directory symlinks. A new request-free UI regression exercises
the actual failed-generation screen without a configured model.

Validation on 2026-10-22:

- Focused backend: 6,352 passed in 347.75 seconds, including 27 additional
  complete-department/map/currency checks, all-map catalog coverage, image/chart
  APIs, starter selection, exclusions, limits, saved templates and SKU compatibility.
- Strict backend types: zero errors; application boot passed.
- Full backend: 22,618 passed and one skipped in 1,134.20 seconds.
- Model-recovery checks: 71 frontend tests passed in two files in 6.72 seconds.
- Final full frontend: 4,252 passed in 248 files in 238.43 seconds. Build passed in
  22.89 seconds; lint retained 19 warnings and zero errors. The earlier frontend
  run was intentionally interrupted before integrating the latest recovery fix.
- Browser automatic hypermarket creation passed with all nine requested
  departments. An additional check of its saved racks confirmed frozen meals in
  freezer displays, dairy/prepared meals/seafood/desserts in refrigerators, and
  breakfast goods/coffee/baking ingredients/barista tools on shelves.
- All 64 actual image endpoints and four galleries were inspected. The automatic
  store's VLM grid displayed photos, names and prices; realistic rendering loaded
  18 images without page errors.
- Browser default artisan-bakery creation used the stocked format without a
  configured model. Saved racks exactly matched the preview including photos.
  Its dense VLM grid displayed all baking-ingredient products with photos and
  readable names/prices; realistic rendering loaded 79 images without page
  errors. Both views were inspected.
- All 56 original image atlases are included in the wheel, verified byte for byte.

Browser product-model availability/replies and persona generation used controlled
fixtures in disposable storage. No live provider completion, local-model download
or paid simulation was invoked.
