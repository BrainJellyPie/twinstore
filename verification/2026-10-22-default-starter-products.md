# Default starter products for new stores

New-store forms now enable automatic catalog selection by default in all six UI locales. The configured
text model sees the store type, description, shelf groups, exclusions and per-category product limits.
Two structured responses select exact categories and SKUs before any project files or persona jobs are
created. Large layouts group equivalent shelves; individual geometry, currency and schedules stay intact.
The user can disable the option to retain format products, including after a model failure. Older API
clients retain format behavior unless they explicitly request automatic selection.

Sixteen more original generated product photos bring the bundled total to 32. Both original atlases
were verified in the built wheel. Product SKUs remain unchanged and uploaded product photos still override
the matching bundled photo.

Validation on 2026-10-22:

- Targeted backend: 632 passed, including all 82 store formats in USD/KRW/JPY, large grouped layouts,
  exclusions, product limits, invalid selections and failures before any project or job is created.
- Backend full run: 17,303 passed, one skipped, four failures in old photo assertions that assumed only
  one product could have any image. Assertions now track the exact uploaded URL and SKU while also
  checking that other bundled photos survive. The complete photo identity and catalog image files then
  passed 56 tests. Combined suite coverage is 17,307 passed and one skipped, not one uninterrupted run.
- Strict backend types: zero errors; application boot passed.
- Frontend: 3,934 passed across 222 files; build passed; lint has 19 existing warnings and zero errors.
- Browser: actual create-store routes/storage with controlled model and persona responses; automatic
  default, failure leaving no partial project, format fallback retry, new automatic café, 320px mobile,
  Korean form, and all 32 images passed. Realistic rendering loaded photos from both atlases with no
  page errors. Screenshots inspected.

No live provider completion was run. The disposable browser server alone substituted deterministic model
and persona responses; production uses the existing configured model client.
