# Existing empty shelves: starter-fill verification

## Source, selection and result

Repository: `BrainJellyPie/twinstore`, branch `feat/operator-modules`. Started clean at `3fa41ef6`.
Integrated main `dcc48c34` (`073d8e58`) and AI UX `6178cc7c` (`e0a23693`). Conflicts in CHANGELOG and
the route import list were resolved by keeping both features; both `assist` and `product_edits` routes
remain registered. The prior `parastore` workspace was not changed. Implementation: `e22dd324`.

The pre-push remote review also found main `0f6b7bb0` and AI UX `4f378798`; these were merged as
`ee426b88` and `4a45ab21`. This is the integration cutoff for this cycle. Route imports and CHANGELOG
entries retain both sides. Run-analysis recovery and routed questions coexist; routed town descriptions
use the existing late-response ownership guard and preserve complete Unicode characters. Two integration
regressions cover routed replies after newer description/density edits; the focused integration run passed
88 tests in 7 files (26.52 s). Later unrelated branch work is left for the next cycle; the destination branch
was checked again after all checks: origin/operator remained `3fa41ef6`, an ancestor of this work.
The non-forced push preserves that history.

The [candidate comparison](2026-10-21-starter-fill-candidates.md) records the user scenarios, source
URLs, current repository workflow and alternative candidates. These are documentation-based hypotheses,
not user interviews, market validation or measured task times. The last cycle edited already stocked
products; this cycle completes manually drawn/imported floors with reviewed starter assortments.

Step 2 now connects rack search/selection, category assignment, reference-product review, server preview,
saving and opening a stocked child layout. The built-in catalog, template SKU factory and existing face
reachability rules are reused. No spreadsheet or model call is required. Original geometry, signs, stocked
racks and existing SKU values/images are preserved. Partly stocked racks are excluded, not topped up.

## Basic validation and separate boundary/fix stage

Basic API flow passed: 1 test in 6.06 s. Basic UI flow passed: 1 test in 2.50 s. Initial strict Python
checking found 3 unused imports after extracting the shared product snapshot reader; they were removed.
The basic TypeScript check and subsequent production builds passed.

The separate API boundary run reproduced **2 failures / 31 passes**: racks outside the floor and racks
overlapping another fixture could still receive products because adjacent reachable tiles alone were
being checked. The fix checks existing geometry validation results before listing/filling racks and asks
the user to repair Step 1. Both reproductions remain in `test_starter_fill_api.py`.

Related regression checking then exposed one stale test mock target after moving the shared snapshot
reader: `find_active_generation` now belongs to `product_sources`. The mock target was updated, retaining
the original active-generation and interrupted-write assertions; no application guard was removed.

Final focused API/domain/template regression run: **85 passed in 16.49 s**, including **43 new starter-fill
cases**, the existing 37 product-editor cases and 5 template identity cases. Final focused frontend:
**28 passed in 3 files, 5.13 s**, including **9 new starter-fill cases** and the existing product-editor tests.

Checked boundaries include:

- Empty, duplicate, missing, unknown, stocked and unsupported rack/category assignments; 100 vs 101
  selections; strict density 1–4 vs zero/negative/fraction/bool/string/null/oversize values and extra fields.
- Sparse empty slots; locked faces, adjacent occupied tiles, disconnected aisles, multi-cell rotation and
  internal faces; Unicode rack identity; invalid bounds/overlap; missing entrance; floor/rack/cell limits.
- Exact existing SKU reuse with custom price/name/promotion/image; ambiguous existing values rejected;
  same names with different SKUs kept separate; small/duplicated catalog pools do not duplicate a SKU in
  a section; deterministic category cycling and template identity compatibility.
- Explicit USD/KRW/JPY reference prices, minor-unit rounding, unsupported currency rejection; layout,
  currency and catalog changes reject old snapshots; active generation and corrupt source files reject
  without replacement; retained building-floor metadata.
- Concurrent same-ID saves, changed-payload conflicts, uncertain response replay, preserving subsequent
  edits to the child, replay after source removal, deleted-child non-resurrection, disk failure after receipt
  reservation, and rejecting excessive output before allocating a copied result.
- Hidden selections across filters; explicit missing-category feedback; invalidated previews after editing;
  background refresh keeps choices; explicit reload/retry replaces the snapshot; choice locking during
  preview; uncertain saves reuse the same request; closing during save does not navigate on completion.

Execution logs: `/workspace/.verification/twinstore-starter-fill/`. Fixtures and reference products are
synthetic scenario inputs, not observed store inventory, real prices or sales effects.

## Required checks before the final remote integration

Frontend uses pinned pnpm **10.33.0** through `npm exec --yes --package=pnpm@10.33.0 -- pnpm ...`.
Tests use one frontend worker because the preceding cycle observed a default-worker 5 s timeout in an
existing assortment UI test. Test timeouts/assertions are unchanged.

| Command | Result |
| --- | --- |
| `cd backend && uv run pyright src/` | 0 errors, 0 warnings |
| `cd backend && uv run python -c "from store_emulator.server.main import app; print('OK')"` | `OK` |
| `cd backend && uv run pytest --basetemp=/workspace/.verification/twinstore-starter-fill/pytest-full` | 15,079 passed, 1 skipped, 689.24 s |
| `cd frontend && pnpm build` | Passed including TypeScript, Vite 20.87 s |
| `cd frontend && pnpm lint` | 0 errors; existing 19 warnings, no new-file warnings |
| `cd frontend && pnpm test --maxWorkers=1` | 3,134 passed in 170 files, 490.21 s |

Build also reports non-failing chunk-size and plugin-time warnings. No costly full simulation was launched.
The skipped case is the existing optional live detector test in `tests/engine/test_capture.py`.

## Revalidation after the final remote integration

| Command | Result |
| --- | --- |
| `cd backend && uv run pyright src/` | 0 errors, 0 warnings |
| Backend application import | `OK` |
| `cd backend && uv run pytest --basetemp=/workspace/.verification/twinstore-starter-fill/pytest-integrated` | 15,113 passed, 1 skipped, 586.88 s |
| `cd frontend && pnpm build` | Passed including TypeScript, Vite 24.05 s |
| `cd frontend && pnpm lint` | 0 errors, existing 19 warnings |
| `cd frontend && pnpm test --maxWorkers=1` | 3,181 passed in 176 files, 416.63 s |

## Browser integration

Reproduce with `starter-fill-browser-seed.py` in a fresh disposable directory (it refuses existing `.data`),
the backend served from that directory with built frontend assets, and `starter-fill-browser-check.mjs`.
The script accepts `PLAYWRIGHT_MODULE`, `CHROMIUM_PATH` and `STARTER_TEST_ORIGIN` overrides.

The fixture has two empty racks, one stocked rack with an explicit custom price/promotion, a registered
synthetic blue 16×16 image, an entrance/exit and a counter. The browser enters Step 2, fills the empty racks,
reviews the 40 planned placements, checks Save access with ordinary wheel scrolling at 1280×900,
1280×640 and 390×844, and injects one lost save response after the real API has written the draft. It then
retries, opens that draft in the existing product editor, and checks the original, geometry, existing SKU
values and image links through the API. The feature browser run passed: 40 new placements, six placements reusing the existing custom SKU/image,
original and non-target racks preserved, and zero page errors. The accepted request and retry returned the
same child layout. All three viewport screenshots were inspected. A replay against the final merged build
also passed with the same checks: `browser-integrated.log` records child
`setup_starter_fc4a3c3cdd9d4e66b7c9db9a02d1393b`, 40 additions, six preserved-SKU placements and
zero page errors. The temporary API server was stopped after verification.

The first browser attempt stopped at a harness locator: Playwright's exact `getByLabel` did not
match the wrapping label/select, while the browser accessibility tree correctly exposed the combobox
as "Category to apply". The check now selects by that exact combobox role/name; no product behavior
was changed for this harness correction.

A second browser failure initially looked like a short-screen scrolling defect. Geometry logs showed
`scrollTop=300` while the available maximum was 534; the pointer near the animated bottom edge was not
reliably delivering wheel events to the dialog. Targeting its side padding at mid-height reached 534 and
made Save visible at 1280×640; 390×844 passed as well. This required a harness coordinate correction,
not a product CSS change. The original viewport and hit-test assertions remain unchanged.

## Limits and next candidate

- Completely empty shelf/fridge racks only; no partial-slot top-up, counter/table fill, physical pack-width
  fitting or cold-chain compatibility inference. Operators choose categories and review the result.
- Reference currencies are USD/KRW/JPY using existing illustrative catalog conversion rules, not live FX.
  No real stock count, actual shelf price or sales impact is inferred.
- Catalog search shows 100 racks; one request accepts 100. Result/source limits are documented in USAGE.
  Mixed existing SKU values must be resolved first. Missing/invalid entrances or geometry require repair.
- Unsaved choices stay only in the open dialog. Save IDs require HTTPS or localhost. An accepted save can
  finish after closing. Receipt-only interrupted writes require checking Layouts and a deliberate new
  preview; removed drafts are never silently recreated. The original layout provides saved-variant undo.
- This module's saves share a lock with each other; other editing flows do not acquire that lock. Snapshot
  checks catch source changes read during preparation; this module always writes a child, never the source.
- No live model, actual store data, physical mobile device, user interview or time-saving measurement was
  used. Browser viewport checks are not physical touch-device validation.
- Next candidate from a different workflow: **resume interrupted/unsent photo work safely**. Inspect current
  queue persistence and browser file-retention requirements before implementing; do not duplicate the
  existing batch upload and combined-capture placement features.

Next-candidate repository evidence: `CaptureUploadQueue.tsx` holds `File` objects and stable request IDs
only in component state/refs and explicitly tells users unsent files are not retained after reload.
A future resume feature must preserve request identity for uncertain uploads and define storage limits,
file reconnection and removal, while reusing the existing 20-photo/100 MB queue and accepted-capture flow.
