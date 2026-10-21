# Combine reviewed shelf photos: verification

2026-10-21. Source: `BrainJellyPie/twinstore`, `feat/operator-modules`. No changes to the old parastore checkout.

## User workflow and scope

[Candidate research](2026-10-21-capture-batch-candidates.md) selected a connected Capture workflow over another analysis worksheet. Operators select existing completed photos, preview their shelf placements and products, save one draft, then explicitly open it. Marketers/researchers can build a photographed store without repeatedly applying individual photos into intermediate drafts. These are document/code-based needs hypotheses, not user interviews or measured time savings.

Existing recognition, crop storage and grid placement are reused. New domain request/preview/save records, application orchestration, API routes, mutation services and UI are connected. The original source layouts and capture files remain unchanged. Batch requests use exact complete normalized product names, including brand/size, for SKU reuse; existing fuzzy matching in single-photo flows remains unchanged.

Integrated heads before full verification: main `5866d60f`, store-scenarios `08ec36e0`, edge-case-loop `7cec5f42`; photoreal-retail `dc9a7805` already included. Operator history through `1155cc12` preserved. Feature commit `361706ab`; integration snapshot `fee2d4ba` followed by boundary/UI fixes.

## Basic, then independent boundary phase

- Initial basic API/storage test exposed fuzzy matching collapsing “Observed tea 0” and “Observed tea 1”. Replaced fuzzy matching only in batch placement with complete normalized-name matching and verified distinct SKUs plus correctly remapped crops. Basic rerun: 1 backend + 1 UI test passed before extending the boundary matrix.
- Boundary red: 5 failures/13 passes exposed oversized resource IDs reaching filesystem errors, legacy currency absent on the layout, missing prices not counted as uncertain, and the grid reducing facings without dropping a product. The initial dropped-product test expectation was corrected to distinguish reduced facings from lost products. Added explicit requested/placed/reduced counts and mandatory reduction acceptance; products dropped entirely still block saving.
- UI boundary red: new draft prepended by a query refresh hid the saved link. Freeze the reviewed base and show success independently of preview visibility. Also removed redundant prefix/subkey invalidations; the overly exact refetch-count assertion initially failed during correction.
- Numeric boundary red: 4 failures/1 pass. Negative stored prices were clamped to zero and NaN/infinite stored recognition data caused uncaught errors. Reject these with a reviewable 409. Genuine zero prices and Unicode names remain valid.
- Extended checks: empty/21/duplicate/traversal/oversized IDs, unknown fields, missing layouts/captures, mixed currency, empty/failed/pending selections, per-item and total facing limits, complete-name SKU reuse versus brand/size variants, stale photo/base snapshots, conflicting request tokens, lost acknowledgement after atomic save, concurrent replays and one-draft preservation. UI checks preview/save failures, exact retry identity, reduction consent, locked input while pending, unmount completion, layout-loading retry and selection invalidation.
- Real Chromium boundary: at 1280×900, Save was at y=989.5 and ordinary mouse-wheel scrolling could not reach it. Auto-scrolling clicks had hidden the problem. Bound the combined panel to 60dvh with native scrolling; the retained browser regression checks ordinary wheel access before clicking.
- Test-fixture issues were fixed separately from product bugs: a missing helper import, missing frontend `readiness` fields caught by TypeScript, and an incomplete backend base-layout fixture caught when opening the real browser page. The API integration now reloads the saved draft through the public setup endpoint as well as inspecting crops/source preservation.

## Executed verification

Logs: `/workspace/.verification/twinstore-capture-batch/`. Final full-suite results are recorded below after completion. Focused backend run before final fixture enrichment: **45 passed, 1 skipped** (24 batch + existing capture engine/API tests). Focused frontend: **23 passed** (9 batch + 14 existing Capture lifecycle tests). The skip is optional Grounding DINO, requiring extra dependencies/weights and explicit opt-in; it was not enabled.

## Browser reproduction

The browser check uses explicit orange-image/offline recognition fixtures, not genuine shelf recognition. On an isolated working directory, seed the `workflow` fixture from `backend/tests/server/test_capture_batch.py` by calling its `__wrapped__(Path.cwd(), pytest.MonkeyPatch())` generator, entering it once then closing it. It seeds the standard sample project and two named captures. Run the backend there with repository `backend/src` on PYTHONPATH and `TWINSTORE_LOCAL_VLM_AUTO=0`, port 18765. Build the frontend first; the backend serves that build on the same origin.

Install Playwright 1.56.1 outside the repository; run [the regression script](capture-batch-browser-check.mjs) from that isolated directory with `PLAYWRIGHT_MODULE=/absolute/path/to/playwright/index.mjs` and `/usr/bin/chromium` (or `CHROMIUM_PATH`). The script selects the fixture base, previews, checks wheel reachability, saves, opens, reloads the saved products via HTTP, and checks a 390×844 mobile preview. Screenshots and logs stay outside git. Never point this fixture script at real user data.

## Limits and next candidate

No live VLM, actual store photos, physical mobile device or actual store data tested. Capture recognition accuracy, time savings, sales effects and general room reconstruction are not claimed. Shelf photos add racks on free floor using existing level/order mapping, at most four racks per photo. Facings can be reduced with explicit consent; whole-product loss blocks saving. Missing prices remain flagged and use a grid zero placeholder until corrected. Same-name matching is not a barcode guarantee. No CSV export is added; the persisted layout is the output.

Source hashes bind a save to the loaded preview content; original sources are never overwritten. Layout save and idempotency record share one atomic JSON file, with a project batch lock. Existing crop storage is shared and assumes the existing single-worker image-manifest model; it is not a multi-file transaction. An unsuccessful layout write can leave newly registered crops. Retry identity lives in the open preview, not a durable browser queue; after reload, inspect Layouts before creating another draft.

Next usability candidate: bounded multi-photo upload queue with per-image status, retry/cancel and clear model requirements, connecting the remaining upload step to this completed review/apply flow. Reassess latest starter-assortment usability before extending it, rather than duplicating the integrated cross-floor assortment feature.
