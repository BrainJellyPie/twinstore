# Category language and everyday product photos

Added 64 photos for hardware, music, gardening, pantry, produce, bakery, dairy,
prepared meals and personal care. The 1,400-product catalog now includes 416 local
photos. All 123 category labels follow the selected interface language, including
the 16 recently added home and hobby categories; stored names, prices and IDs stay intact.

Merged main through c12c4b1 (0.4.7) and integrated completed starter-fill localization
from 3f25ef8. Automatic defaults, two-step model selection, picture previews, language
changes and save retries remain covered. Translation-key ownership checks catch
overlapping catalogs that could silently alter labels or placeholders.

Validation on 2026-10-22:

- Targeted backend: 3,120 passed in 190.12 seconds, including catalog selection,
  photos and legacy stores, starter placement and the new marketing audit cases.
- Strict backend types: zero errors; application boot passed.
- Full backend: 19,811 passed, one skipped in 970.42 seconds.
- Targeted frontend: 92 passed, including all six languages selecting the 16 newer
  categories in a KRW store without changing raw category IDs or stored product names.
- Full frontend: 4,110 passed in 235 files; build passed in 20.80 seconds; lint
  retained 19 warnings and zero errors.
- Browser: new-store automatic defaults and all 15 selected departments passed.
  Actual shelf-preview API, 64 image endpoints, four photo galleries and the VLM
  chart passed and were visually inspected.
- Six-language starter workflow passed at 390 and 1280 px widths. All 123 category
  IDs and localized labels were checked; each actual save placed 40 products. An
  intentionally lost save response was retried with the same accepted result, preserving
  original layouts and reused names, prices, promotions and photos. Representative
  Korean and French screenshots were visually inspected.
- Realistic rendering loaded 30 bundled photos without page errors; visually inspected.
- All 26 original atlases are included in the wheel. Photo bindings and complete
  coverage of all 123 backend category IDs by the UI label mapping were verified.

Browser product-model/persona replies were controlled fixtures. No live provider
completion or paid simulation was invoked.
