# More complete menu photos in default maps

Added 64 local menu photos, bringing the catalog to 704 pictures for 1,496 entries
in 131 categories. Ice-cream, Turkish, pizza, salad, juice, Indian and Thai menus
now have pictures for every existing product. Seven additional Mexican products
are pictured too. The matching default maps already stock these products, so
previews, saved floors and VLM grids inherit the pictures without changing product
names, prices or SKU identities. Complete-menu coverage now checks 13 formats in
three currencies.

Integrated completed upstream fixes for deleted samples and unwanted model calls
(e63b0f9b), repeated model failures (11c2ac1c, 654fac2b), damaged project metadata
(354ddea5), natural design/recovery translations (28dd9f5f), and test timeouts for
large forms (c5d1f678). Preserved the expanded catalog, all 131 category labels,
existing currency/interval regressions and source-layout preservation.

Integration testing found that a translated template heading did not carry into
its downloaded SVG title. The export now uses the displayed heading without
mutating the stored name. Also removed a duplicate test import and a conflicting
model-state fixture, and updated expectations for the revised Korean copy.

Validation on 2026-10-22:

- Focused backend: 4,774 passed in 314.48 seconds, including default-map coverage,
  39 complete-menu checks, exclusions, limits, image/chart APIs, saved templates,
  damaged files, sample seeding and model-failure handling.
- Strict backend types: zero errors; application boot passed.
- Full backend: 21,519 passed and one skipped in 1,130.04 seconds.
- Initial full frontend: 4,220 passed and eight failed. After the integration fixes,
  all 92 affected tests passed in 8.64 seconds, followed by all 4,228 frontend tests
  in 244 files in 232.19 seconds. Build passed in 21.23 seconds; lint retained
  19 warnings and zero errors.
- Browser automatic diner creation passed with all eight requested menu categories.
  All 64 actual image endpoints and four galleries were inspected. Its VLM grid
  showed photos, names and prices; realistic rendering loaded 16 images without
  page errors.
- Browser default pizzeria creation used the format assortment with no configured
  model. Saved racks exactly matched the preview. Its dense VLM grid showed all
  12 menu products with photos and readable names/prices; realistic rendering
  loaded 43 images without page errors. Both views were inspected.
- All six languages at 390px and 1280px passed options JSON export/import,
  negative seeds, individual weekday hours, category exclusions, global/category
  limits and source-layout preservation. Interior colors survived preview, SVG
  export and saving; translated SVG titles preserved original store data. Korean
  mobile and French desktop screens were visually inspected for both flows.
- All 44 original image atlases are included in the wheel, verified byte for byte.

Browser product-model availability/replies and persona generation used controlled
fixtures in disposable storage. No live provider completion, local-model download
or paid simulation was invoked.
