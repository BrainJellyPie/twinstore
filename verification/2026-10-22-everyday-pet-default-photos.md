# Everyday and pet photos in default maps

Added 64 local photos, bringing the catalog to 832 pictures for 1,496 entries in
131 categories. Health/beauty, wellness, baby care, hair care, pet care, pet
enrichment, plant-based food, artisan snacks, craft refreshments and car care now
have a photo for every existing item. Their stocked default maps inherit these
photos without changing product identities or prices.

Integrated completed upstream fixes for tabs left open across an update
(f98b977f) and localized open-area editing/floor reviews with known dimensions
(5712d139). The integration preserves the newer model-readiness tests, catalog
category translations, no-model format defaults and existing verification notes.
The real-browser floor review check now compares saved products with previews
including their image URLs, rather than removing photos before comparison.

Validation on 2026-10-22:

- Integration checks: 125 frontend tests passed in seven files in 13.55 seconds.
- Focused backend: 5,993 passed in 331.59 seconds, including 30 new complete
  department/map/currency checks, all-map catalog coverage, image/chart APIs,
  starter selection, exclusions, limits, saved templates and SKU compatibility.
- Strict backend types: zero errors; application boot passed.
- Full backend: 22,259 passed and one skipped in 1,105.00 seconds.
- Full frontend: 4,250 passed in 248 files in 236.65 seconds. Build passed in
  22.17 seconds; lint retained 19 warnings and zero errors.
- Browser automatic hypermarket creation passed with all ten requested
  departments. All 64 actual image endpoints and four galleries were inspected.
  The VLM grid displayed photos, names and prices; realistic rendering loaded
  20 images without page errors.
- Browser default pet-superstore creation used the stocked format with no model
  configured. Saved racks exactly matched the preview including photos. Its VLM
  grid showed pictured pet food, treats, grooming supplies and toys; realistic
  rendering loaded 38 images without page errors. Both views were inspected.
- Open-area editing, floor review, SVG export, building settings export and
  actual two-floor saving passed in all six languages at 390px and 1280px widths.
  Names, coordinates, schedules and pictured products survived preview/save;
  the source floor stayed unchanged. Korean mobile and French desktop screenshots
  were inspected, with no horizontal overflow or page errors.
- All 52 original image atlases are included in the wheel, verified byte for byte.

Browser product-model availability/replies and persona generation used controlled
fixtures in disposable storage. No live provider completion, local-model download
or paid simulation was invoked.
