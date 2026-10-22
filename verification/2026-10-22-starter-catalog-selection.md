# Starter catalog and automatic product selection

Added 144 generic products across 12 categories: 824 catalog entries in 75 categories in total.
Sixteen original AI-generated packshots are bundled as `assets/catalog/starter-01.png`; the image API
serves individual cells locally. The wheel was inspected to verify that the atlas is included.

The Step 2 button now opens with automatic selection as its default. The configured text model assigns
categories to eligible empty racks, then selects exact existing catalog SKUs. Both responses are validated.
Preview and save use those ordered SKUs; existing stocked racks, product values and geometry remain intact.
Opening the dialog does not call a model. Manual selection remains available, including after model failures.

Validation on 2026-10-22:

- Targeted backend: 343 tests passed, including 75 categories × 3 currencies, invalid model responses,
  stale sources during selection, SKU bounds, retry-safe saves, image decoding and unknown image paths.
- Frontend: 3,841 tests passed across 214 files after the package-classification fix; build and strict
  type checks passed. Lint retained 19 existing warnings with no errors.
- Backend full run: 17,012 passed, one skipped, three failures in a legacy checkout fixture. That fixture
  excluded the entire global catalog, exceeding the 64-selection request limit after catalog growth.
  It now excludes only categories used by its store format, preserving its original checkout-capacity
  assertion. The complete affected file then passed all 271 tests. Combined suite coverage: 17,015
  passed and one skipped; this was not one uninterrupted passing run.
- Browser: controlled model replies (failure and recovery), real preview/save/image APIs, automatic default,
  320px mobile layout, image loading, uncertain-save retry and original-layout preservation passed.
- Realistic rendering loaded all three expected bundled images without page errors; screenshots inspected.

Bugs found and fixed during validation: manual mode reset after explicit reload; late automatic responses
starting a preview after dialog closure; coffee beans appearing as cans and oat cartons as bottles in 3D.
Bundled image identities now retain their package type even when names are localized or edited.

No live provider completion was run: the QA environment has no configured model API key. Structured model
responses were controlled in engine/API/browser tests; production uses the application's existing text-model client.
