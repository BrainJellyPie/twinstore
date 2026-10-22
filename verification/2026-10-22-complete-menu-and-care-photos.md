# Complete menu and care photos in default maps

Added 64 local photos, bringing the catalog to 768 pictures for 1,496 entries in
131 categories. All 18 menu assortments now have a photo for every existing item.
First aid, nutrition supplements, oral care, care supplies, bath/body and pharmacy
care assortments are fully pictured too. The matching default maps already stock
these products; previews, saved floors and VLM grids inherit their photos without
changing names, prices or SKU identities.

Integrated completed upstream fixes that keep earlier complete llama.cpp runtimes
(e02444ea), migrate the runtime with existing model files (dd09c2e3), omit reused
persona IDs that refer to different people from run comparisons (a554b0d5), and
show whether a saved local model address currently answers (75867b9c).

Boundary testing reproduced a server error for four malformed IPv6 addresses in
saved local-provider settings. The provider list now remains available, showing
the enabled address as not running; disabled providers are not checked. Eight
request-level regressions cover both states for all four addresses.

Validation on 2026-10-22:

- Focused backend: 5,058 passed in 305.45 seconds, including all default-map catalog
  coverage, 54 complete-menu checks and nine care-map/currency checks that each
  verify six complete departments, exclusions, limits, image/chart APIs, saved
  templates, old local runtimes, comparison identities and provider checks.
- Provider-specific regressions: 11 passed in 4.10 seconds.
- Strict backend types: zero errors; application boot passed.
- Full backend: 21,897 passed and one skipped in 1,057.19 seconds.
- Full frontend: 4,230 passed in 244 files in 233.58 seconds. Build passed in
  22.05 seconds; lint retained 19 warnings and zero errors.
- Launcher: Go tests passed in 10.102 seconds; vet passed; Windows amd64 and
  macOS arm64 binaries cross-compiled successfully.
- Browser automatic pharmacy creation passed with all six requested care
  categories. All 64 actual image endpoints and four galleries were inspected.
  The VLM grid showed photos, names and prices; realistic rendering loaded
  14 images without page errors.
- Browser default Vietnamese café creation used the stocked format with no model
  configured. Saved racks exactly matched the preview. Its dense VLM grid showed
  all 12 menu products with photos and readable names/prices; realistic rendering
  loaded 43 images without page errors. Both views were inspected.
- All 48 original image atlases are included in the wheel, verified byte for byte.

Browser product-model availability/replies and persona generation used controlled
fixtures in disposable storage. No live provider completion, local-model download
or paid simulation was invoked.
