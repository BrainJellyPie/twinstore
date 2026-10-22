# Localized automatic placement and more product photos

Merged main through f7b4771 (0.4.6), preserving automatic starter selection,
preview photos, retry identity and the existing bulk editor's localized validation.
Automatic placement now has complete display text in all six UI languages and
uses the selected locale to format prices. API identifiers and prices are unchanged.

Added 64 photos for groceries, baby care, pets, stationery, art, electronics,
travel, games, cameras, coffee equipment and household tools. The catalog contains
1,304 products in 115 categories, with 320 bundled photos. Existing exact SKUs
receive these photos through the established fallback without rewriting saved layouts.

Validation on 2026-10-22:

- Targeted backend catalog, automatic selection, template, photo, legacy-layout,
  Shelf Lab and neighborhood checks: 2,487 passed in 139.41 seconds.
- Strict backend types: zero errors; application boot passed.
- Full backend: 19,244 passed, one skipped in 952.37 seconds.
- Targeted frontend: 99 passed. All six languages retain automatic defaults,
  preview photos and request values; language changes during pending selection,
  failed saves and manual validation preserve choices and retry identity.
- Full frontend: 4,068 passed in 232 files; build passed; lint retained 19 warnings
  and zero errors.
- Browser: new-store automatic defaults, all 15 selected departments, actual
  shelf-preview API photos and all 64 new image endpoints passed. Four photo
  galleries and the VLM chart were visually inspected.
- Korean automatic placement passed at 390 px width with requirement text,
  preview photos, no horizontal overflow and no page errors; visually inspected.
- Realistic rendering loaded 30 bundled images without page errors; visually inspected.
- Wheel includes all 20 original photo atlases; catalog totals verified.

Browser model/persona replies were controlled fixtures. No live provider completion
or paid simulation was invoked.
