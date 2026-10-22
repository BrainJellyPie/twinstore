# Reviewed library photos: implementation and verification

## Result and selection

**Step 2 → Use library photos** connects the existing Market → Products upload library to actual
placed products. Search products/photos, use only unique existing SKU links as suggestions, choose
manually for ambiguity, inspect before/after, save/open a separate layout. Existing images are
protected unless replacement is enabled. No model calls, inferred prices or inventory counts.
See [candidate comparison](2026-10-22-library-photos-candidates.md) and
[usage](../USAGE.md#reuse-uploaded-product-photos-on-a-layout). Source-based requirements hypothesis;
no interviews, task-time measurements, sales impact or marketing effectiveness claims.

- Domain validates exact assignment identifiers, unique SKUs, strict replacement flag and batch limits.
- Engine changes only image URLs, across all placements of a SKU, retaining names/prices/promotion/order.
- Application snapshots selected PNG bytes into content-addressed project files and saves a child layout.
  Full source/manifest digest plus selected photo/link versions reject stale work. Save IDs and receipts
  prevent duplicate or resurrected drafts; another source/changed choices cannot reuse an identity.
- HTTP provides options/preview/save and immutable snapshot image access. Frontend uses query/mutation
  services, resets previews when choices change, retains hidden selections, and ignores late results
  after close/layout switch. Reviewed immutable snapshot URLs take priority over project image manifests; other SKU photos
  continue following current upload versions.
- Source photos and source layouts remain intact. Snapshot copies survive later library deletion.

Implementation commit: e3e2b383; manifest-refresh compatibility fix: 38038473. Integration commit
006ce6da includes origin/main 6f83ad39 and origin/feat/ai-ux-loop 4dcc867b. Final integration commits
21d660a6 and e05d82f1 include origin/main 304e44b5 and origin/feat/ai-ux-loop a685873b. Existing
operator work from 04821954 is retained. Conflict resolution kept the tested observable UI harnesses,
AI UX README/0.4.1 changelog organization, operator guides and unreleased photo/reuse features.
The last two merges add rack-copy regression tests, verification notes and the launcher's ready-state
Open TwinStore button; backend/frontend production code is identical to the fully validated 38038473.
The destination operator branch is checked again immediately before push.

## Basic verification, then separate boundary/repair phase

Initial end-to-end API checks: **3 passed** (`basic-backend.log`); initial component workflow checks:
**3 passed** (`basic-frontend.log`). Then boundary suites were added and run separately.

Reproduced failures and fixes:

1. `__proto__` as a SKU disappeared when suggested choices used a plain JS object. The red UI suite
   failed 1/14 cases. Replaced that mapping with `Map`; `__proto__`, `constructor`, `toString` are ordinary
   SKUs. Regression also verifies the request contains the exact selected SKU.
2. A stored library metadata JSON array caused an unhandled `AttributeError` instead of actionable
   failure. Translate unreadable package metadata at this workflow boundary to HTTP 409; source unchanged.
3. An existing but damaged snapshot file was reused and served as though it were the verified PNG.
   Verify size/hash before reuse and atomically restore the exact verified library bytes when needed.

4. A later audit reproduced a stale URL for an **unselected** product after another SKU-image upload:
   the new layout had captured a resolved manifest URL and the first implementation preserved every
   stored URL. `manifest-refresh-red.log` records the failing version comparison. Centralized layout
   image resolution now pins only immutable photo snapshots; other photos follow the current manifest
   version, with stored URLs as fallback. Selected snapshots remain unchanged. Interrupted the ongoing
   backend full run (no earlier failures) and restarted full validation after this fix.

Backend red suite: 3 failures/33 passes. Two were bugs above; the third was a boundary test fixture
that put 101 items in a slot whose existing domain limit is four. Corrected the fixture to 26 valid
racks, retaining the 100/101 SKU batch test. Do not count that fixture error as a product defect.
After fixes: **78 passed** (new API + rack-copy + playback suites); final expanded API boundary suite:
**40 passed**, with **82 passed** across affected API/rack-copy/playback suites after the compatibility fix. UI suite after repair/search addition: **15 passed**.

Verified boundaries: empty library/layout; exact Unicode and special JS-key SKUs; duplicate names
without name-based matching; duplicate/unknown/blank/oversized/non-string SKU; empty/missing lists;
strict boolean/invalid digest/unknown fields; zero and largest safe integer prices retained; 100/101
assignments; actual 500/501 library photos; photo/batch byte ceilings including exact limit; corrupt
PNG/metadata/snapshot; removed/renamed/relinked/changed photo; source names/prices/currency/manifest
changes; image replacement opt-in; invalid second assignment prevents first applying; lock conflicts;
two concurrent identical saves and retry; receipt reuse across layouts/different bodies/deleted child;
interrupted disk write; missing project/hash; filtered choices; stale refreshed revisions; API loading,
preview and save errors; double-action locking; close/layout switch while saving. Existing unrelated
image manifests cannot clear a saved layout photo. Image deletion after save cannot break the copy.

## Browser integration

`library-photos-browser-seed.py` seeds only a synthetic fixture into a fresh disposable directory;
`library-photos-browser-check.mjs` uses real backend APIs and the built app:

1. Market → Products: upload a synthetic PNG via the file input, explicitly disable background removal
   and optional model reading (no live model calls).
2. Open the stocked fixture → Step 2 → Use library photos → choose a photo → preview.
3. Verify the PNG loads and the save button is visible/reachable at 1280×900, 1280×640 and 390×844.
4. Let the real server accept save, abort its response, retry, and open the single saved child layout.
5. Delete the original library image via API; saved image URLs still return 200. Compare source and child
   data: only chosen images differ, all prices/order/geometry preserved. Source layout unchanged.

Passed with zero page errors; the 390×844 screenshot visually inspected and all three viewports checked automatically. Re-run instructions:
use backend Python to seed an empty working directory, start uvicorn there with `TWINSTORE_LOCAL_VLM_AUTO=0`,
build frontend, then run the Node check with `PLAYWRIGHT_MODULE` set to the installed Playwright module
and optionally `PHOTO_TEST_ORIGIN` (default http://127.0.0.1:18771).

## Required checks

Actual integrated checks: frontend on 006ce6da; backend and browser repeated on the identical frontend
plus the backend-only compatibility fix 38038473.

| Check | Actual result | Log |
| --- | --- | --- |
| `uv run pyright src/` | 0 errors, 0 warnings | `pyright.log` |
| App import boot (`from store_emulator.server.main import app`) | OK, 226 routes | `import.log` |
| `uv run pytest` after the compatibility fix | 16,420 passed, 1 skipped, 606.55 seconds | `backend-full.log` |
| `pnpm build` | Passed; existing large-chunk / Babel plugin-time notices | `build.log` |
| `pnpm lint` | 0 errors, 19 existing warnings; none in this feature | `lint.log` |
| `pnpm test --maxWorkers=1 --reporter=verbose` | 203 files, 3,743 passed, 455.72 seconds | `frontend-full.log` |
| Release workflow local regression | 7 passed | `release-workflow.log` |
| Launcher `go test -p 1 ./...` | Passed (1.545 seconds) | `launcher.log` |
| Built-app browser integration after final build | Passed, 3 viewports, no page errors | `browser-final.log` |

Final merge verification on e05d82f1 (the backend/frontend production code has not changed):

| Check | Actual result | Log |
| --- | --- | --- |
| Rack-copy engine/API, library-photo API and playback regressions | 327 passed, 15.38 seconds | `final-integration-backend.log` |
| LibraryPhotos, RackCopy, LayoutBriefField and routedDraftLifetime component suites | 4 files, 67 passed, 26.83 seconds | `final-integration-frontend.log` |
| `pnpm build` | Passed, 24.73 seconds; same existing chunk/plugin notices | `final-integration-build.log` |
| `pnpm lint` | 0 errors, the same 19 existing warnings | `final-integration-lint.log` |
| Launcher `go test -p 1 ./...` | Passed, 1.684 seconds | `final-integration-launcher.log` |
| Extracted launcher boot script `node --check` | Passed | `boot-inline.js` (checked input) |

Fixed package manager: pnpm **10.33.0**, invoked through `npm exec --yes --package=pnpm@10.33.0 -- pnpm`.
Full frontend tests used one worker to avoid competing with other resource-heavy checks. The interrupted
backend run before the compatibility fix is not counted as a completed full check. The preinstalled `/usr/bin/go` was not the Go compiler
(`Go: Unknown option: test`); installed official go1.27.3 into a task-local tools directory, verified the
release archive SHA256, and successfully ran launcher tests with that compiler.

Logs and screenshots are local at `/workspace/.verification/twinstore-library-photos/`; no generated
data or credentials are committed.

## Limits and next candidate

This reuses existing packshots; it is not shelf-photo reconstruction, barcode verification or live
recognition accuracy testing. No real store/model/panel validation or time savings measurement was done. The existing optional
Grounding DINO test requires the capture extra plus `PARASTORE_TEST_GDINO=1` and a roughly 700 MB
model download; it was not enabled for this model-free workflow.
500-photo library, 100 selected SKUs, 8 MB/photo and 64 MB summed assignment bytes. Preview snapshots
remain with the project even when the preview is abandoned. Normal project deletion removes them.
No cross-device restore for unfinished choices. Existing workbook export has an empty image column;
this cycle does not add image embedding/export. Browser coverage uses the supported classic renderer;
photoreal GPU appearance and all six language surfaces are not separately validated here.

Next different convenience candidate: opt-in restoration of unfinished product edits, with source revision
checks and conflict-aware recovery, following the existing capture-queue recovery pattern. Code evidence: ProductBulkEditor mounts its
ProductSession only while the dialog is open and keeps drafts/history in component state; it currently
has no persistent draft store. New image
filename/SKU matching remains a later first-import candidate; avoid another recognition/upload queue.
