# Complete menu photos in default restaurant maps

Added 64 local photos, bringing the catalog to 640 pictures for 1,496 entries in
131 categories. Tea, burger, noodle, restaurant, sushi and bubble-tea assortments
now have pictures for every existing menu product. Five additional Turkish-menu
products are pictured too. Their default maps already stock these products, so
the photos appear in previews, saved layouts and VLM shelf grids without changing
product names, prices or SKU identities.

Integrated completed launcher/data-upgrade fixes (b01ba2e), same-IP page access
(591afe8), startup model guidance (6f3d9c63), model-aware new-store defaults
(2cec59ed), damaged-file recovery (6fb42702), and remaining layout/persona/run
localization (c62cfa96). Kept all 131 translated category mappings, existing
localized SVG exports, live error translations and source-layout preservation.
Configured models select starter products by default; without a model, the
wizard starts from the stocked format assortment. Explicit choices remain
available, and opening the form does not download a local model.

Boundary checking found that four malformed Origin values raised a server error
in the new same-IP check. The parser now refuses them with 403, with request-level
regressions. Product classification also keeps renamed hot meals out of frozen
food categories and distinguishes an empty tea cup from drinks.

Validation on 2026-10-22:

- Focused backend: 4,337 passed in 260.27 seconds. This includes catalog coverage
  across all 82 default maps, three currencies and three seeds, 18 complete-menu
  checks, exclusions, limits, small layouts, image/chart APIs, saved templates,
  origin validation and damaged-file recovery.
- Strict backend types: zero errors; application boot passed.
- Full backend: 21,153 passed and one skipped in 1,065.76 seconds.
- Focused frontend: 93 passed in three files. Full frontend: 4,199 passed in
  242 files in 227.15 seconds. Build passed in 21.67 seconds; lint retained
  19 warnings and zero errors.
- Launcher: Go tests passed in 10.080 seconds; vet passed; Windows amd64 and
  macOS arm64 binaries cross-compiled successfully.
- Browser automatic food-hall creation passed with all seven requested menu
  categories. All 64 actual image endpoints and four galleries were inspected.
  Its VLM grid showed pictures, names and prices; the realistic view loaded
  14 images without page errors.
- Browser new-store creation with no model selected the format assortment by
  default. The sushi map's saved racks exactly matched its preview. Its VLM grid
  showed all 12 sushi menu products with photos and readable names/prices;
  realistic rendering loaded 37 images without page errors. Both were inspected.
- Six languages at 390px and 1280px passed individual weekday hours, category
  exclusions, global/category-specific limits, negative seeds, options JSON
  export/import, preview/save equality and source-layout preservation. Korean
  mobile and French desktop controls were visually inspected.
- All 40 original image atlases are included in the wheel, verified byte for byte.

Browser product-model availability/replies and persona generation used controlled
fixtures in disposable storage. No live provider completion, local-model download
or paid simulation was invoked.
