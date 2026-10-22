# Drinks and dessert photos in default maps

Added 64 local photos for water, sports and energy drinks, coffee, soda, tea,
beer, wine, frozen food and ice cream. The catalog now has 576 images for 1,496
entries in 131 categories. Existing convenience, grocery, cafe and dessert maps
use the photos through their stocked catalog products, without changing product
names, prices or SKU identities. VLM grids show the same pictures with item names
and prices; realistic views use matching package shapes.

Integrated completed template-hours/assortment/options-file localization
(d00abd1), browser UI cache revalidation (3d9779f), and explicit local-model
start/stop choice (be8370d). All 131 category mappings and the eight recent
baby/toy translations remain available after the shared-label helper moved.

Validation on 2026-10-22:

- Focused backend: 4,058 passed in 235.28 seconds. Coverage includes every catalog
  product/photo across all 82 default maps, three currencies and three seeds;
  exclusions, small layouts, per-category limits, actual image/chart APIs,
  automatic selection, saved templates, local-model choices and UI caching.
- Strict backend types: zero errors; application boot passed.
- Full backend: 20,763 passed, one skipped in 1,055.48 seconds.
- Focused frontend: 70 passed in three files. Renaming a pictured item preserves
  drink/ice-cream/frozen-food classification, coconut-can shape and beer multipack.
- Full frontend: 4,146 passed in 239 files in 220.00 seconds; build passed in
  20.59 seconds; lint retained 19 warnings and zero errors.
- Browser automatic flow passed with six target drink/frozen departments. All
  64 image endpoints and four galleries were checked and visually inspected.
  The actual VLM chart and realistic view were inspected; 17 images loaded with
  no page errors.
- Browser format-default convenience map passed with automatic selection disabled.
  Saved racks exactly matched the template preview. Its VLM grid showed the water
  assortment with photos, readable names and prices. The realistic view loaded
  87 images with no page errors; both views were inspected.
- Template options passed in English, Korean, Chinese, Japanese, Spanish and
  French at 390px and 1280px: individual 00:00–24:00 hours, category exclusion,
  global and category-specific item limits, negative seed, JSON export/import,
  matching preview/save results, and preservation of the source layout. Korean
  mobile and French desktop controls were visually inspected.
- The wheel contains all 36 original image atlases, verified byte for byte.

Browser product-model and persona replies used controlled fixtures in disposable
storage. No live provider completion, local-model download or paid simulation
was invoked.
