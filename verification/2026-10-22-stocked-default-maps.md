# Expanded catalog on the default maps

The 82 default map templates now stock the expanded catalog in departments suited
to each format. Toy and hobby stores include vehicles, plush toys, educational toys,
puzzles, model building and miniature painting; baby stores include feeding and bath
supplies. Pharmacy, café, grocery, home, pet, electronics, craft and sports templates
also include the corresponding newer products. Format defaults work without a
product-selection model call and remain available alongside automatic selection.

Added 96 baby, toy and hobby products with 32 photos and category labels in six
languages. The catalog contains 1,496 entries in 131 categories and 448 local photos.
Some existing products appear in more than one category: the entries represent
1,493 distinct stable SKUs. Across the ready-made maps, every catalog SKU and its
available image appears, in USD, KRW and JPY and with multiple layout seeds.

Integrated completed floor-preview, comparison and SVG localization from fe24c44.

Validation on 2026-10-22:

- Catalog/selection/image targets: 3,209 passed in 170.31 seconds.
- Template targets: 4,116 passed initially; two older fixed-category expectations
  were updated for the expanded assortments. The affected API and format tests
  then passed (35 tests). New coverage checks every catalog product/photo across
  all maps, matching specialty departments, 8×6 floors, exclusions and product
  limits, plus preview/save/reuse equality in three currencies.
- Strict backend types: zero errors; application boot passed after template changes.
- Full backend: 20,068 passed, one skipped in 1,010.55 seconds, with six failures
  exposing two removed legacy departments. Restored souvenirs alongside the new Nordic
  home assortment and soft drinks alongside craft refreshments in the Mexican restaurant.
  All 285 affected format, size/style, currency, limit and complete-catalog cases then
  passed in 17.47 seconds; the full suite was not repeated after these two list fixes.
- Full frontend: 4,125 passed in 236 files; build passed in 22.86 seconds; lint
  retained 19 warnings and zero errors. No frontend source changed after these checks.
- Browser automatic new-store flow selected all eight new categories. All 32
  image endpoints, both galleries and the actual VLM shelf grid passed and were
  visually inspected. Realistic rendering loaded 16 images without page errors.
- Browser format-default new-store flow explicitly disabled automatic selection.
  New toy/hobby departments were stocked immediately; the saved rack contents
  exactly matched the template preview. The actual VLM grid included pictured and
  unpictured products. Realistic rendering loaded 41 images without page errors.
  Both the default-map grid and realistic view were visually inspected.
- Floor previews/comparison/SVG export passed in six languages at 390 and 1280 px.
  Saved rack contents matched previews and original layouts were preserved.
  Korean and French screenshots were visually inspected.
- The wheel includes all 28 unmodified image atlases.

Browser product-model and persona replies used controlled fixtures in disposable
storage. No live provider completion or paid simulation was invoked.
