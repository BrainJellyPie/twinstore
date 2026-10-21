# Placed-product bulk editing — verification

## Scope and integration

This cycle works in `BrainJellyPie/twinstore`, branch `feat/operator-modules`. The prior
`parastore` workspace is untouched. The starting operator commit was `24fea6d9`.
Main `113ab237` and AI UX `877ac758` were integrated before implementation; AI UX
`a556a035` was integrated before the full required checks, yielding `a71bacc9`.
The implementation is `90727f73`; catalog-retry recovery and the strengthened browser regression
are `42267fb7`. No forced update or remote deletion is used.
The later pre-push inspection still found operator at `24fea6d9`. Independently running branches had
advanced main to `0912816b` (scenario/model-key fixes) and AI UX to `0562a5f3` (interviews/home tiles).
Those later unrelated changes are outside this cycle's verified application snapshot; they remain on
their remote branches for the next integration cycle. No remote result is overwritten.

The [candidate comparison](2026-10-21-product-editor-candidates.md) records the workflow inspection,
public sources, user scenarios and selection rationale. These are source-based requirements
hypotheses, not interviews, measured task times or market validation.

The existing stocked-draft dashboard now connects search/selection, explicit name/price/promotion
edits, server preview, save and opening the new child layout. It needs no spreadsheet authoring or
model call. Original layouts, unedited products, geometry, SKU identity, regular prices and product
images are preserved. All placements of an exact SKU change together; this is not rack-specific editing.

## Basic checks, then boundary/fix stage

Basic API flow: 1 passed (4.87 s). Basic UI flow: 1 passed (3.24 s). Initial strict Python checking
passed. Initial TypeScript checking found use of `Array.at`, unsupported by the repository target;
replaced it with indexed access before the build passed.

The separate boundary stage reproduced and fixed these defects:

| Reproduction | Correction | Regression evidence |
| --- | --- | --- |
| A slow catalog refetch unmounted the form and lost local edits | Keep the existing form mounted and its editing snapshot stable during background refresh | `refetch-red.log`: 2 failed / 5 passed, then final UI suite green |
| Catalog reload failures were hidden behind previously cached data | Show the error and an explicit retry while retaining the draft | Initial boundary UI: 1 failed / 16 passed; final UI suite green |
| Explicit discard/reload still allowed edits while waiting, which could later disappear | Lock editing, undo, preview and save while that explicit reload is pending | `reload-red.log`: 1 failed / 17 passed; final UI suite green |
| A malformed JSON or top-level array in the stored source caused an unhandled failure | Return an actionable 409 without rewriting the stored source | `corrupt-red.log`: 2 failed; final focused backend: 37 passed |
| Retrying a failed explicit catalog reload fetched new data but retained the stale editing snapshot | Route the clearly labelled discard-and-retry action through the same locked reload/remount path | `retry-red.log`: 1 failed; `ui-final.log`: 19 passed |

Focused backend: **37 passed (7.92 s)**. Final focused frontend: **19 passed in 2 files (2.93 s)**.
The cases exercise:

- Empty/missing/duplicate/unknown SKUs; mixed existing values; Unicode names and exact SKU identity;
  partial patches, explicit promotion clearing and no-op saves.
- Zero, negative, fractional, boolean, string, NaN/infinite and unsafe prices; exact decimal half-up
  rounding in USD/KRW; JavaScript safe-integer bounds and long invalid inputs.
- 500 vs 501 edited SKUs; 5,000 vs 5,001 catalog SKUs; 50,000 vs 50,004 placements.
- Source/currency changes and removals; active layout generation; corrupt stored JSON; disk-write
  interruption; same-ID concurrent requests; changed-payload rejection; retry after a source disappears;
  no resurrection of deleted drafts and no overwrite of later edits to an accepted draft.
- Hidden selections across search, undo, preview invalidation after editing, uncertain-save replay with
  the identical request, explicit reload locking and dialog closure while a request is pending.
- API preview → saved child → reopen, exact preservation of original/unselected values, parent linkage,
  and a real registered synthetic image still accessible from the saved layout.

Logs are in `/workspace/.verification/twinstore-product-editor/` for this execution environment.
Synthetic fixtures exercise behavior; they are not real inventory, observed prices or sales outcomes.

## Required checks

Backend checks executed on the integrated application at `a71bacc9`. The only subsequent application
change is the frontend catalog-retry correction above; frontend checks are repeated at `42267fb7`.

| Command | Result |
| --- | --- |
| `cd backend && uv run pyright src/` | 0 errors, 0 warnings |
| `cd backend && uv run python -c "from store_emulator.server.main import app; print('OK')"` | `OK` |
| `cd backend && uv run pytest --basetemp=/workspace/.verification/twinstore-product-editor/pytest-full` | 14,930 passed, 1 skipped in 694.77 s |
| `cd frontend && pnpm build` | Passed again after retry fix, including TypeScript; Vite 21.93 s |
| `cd frontend && pnpm lint` | 0 errors, 19 pre-existing warnings; no new-file warnings |
| `cd frontend && pnpm test --maxWorkers=1` | 2,996 passed in 162 files, 368.77 s |

Frontend commands use the repository's pinned pnpm **10.33.0**, invoked through
`npm exec --yes --package=pnpm@10.33.0 -- pnpm ...`. Build also reports non-failing chunk-size/plugin-time
warnings. No expensive full simulation was launched.
The one backend skip is the opt-in Grounding DINO capture test, which requires the capture extras,
`PARASTORE_TEST_GDINO=1` and a roughly 700 MB model download; it is unrelated to product editing.
The first default-worker frontend run completed with 2,995 passed / 1 failed in 174.99 s: the existing
`BuildingAssortment` two-floor test exceeded its 5,000 ms test timeout. No assertion failed in the new
product editor. The isolated assortment suite then passed all 10 tests in 12.84 s. The full single-worker
rerun passed all 2,996 tests without increasing timeouts, weakening assertions or changing the existing
assortment implementation. The default-worker timeout remains recorded as an execution limitation.

## Browser integration

Use `product-editor-browser-seed.py` in a fresh disposable directory (it refuses an existing `.data`),
start the backend with that directory as cwd and built frontend assets available, then run
`product-editor-browser-check.mjs` there with Playwright and Chromium installed. The script accepts
`PLAYWRIGHT_MODULE`, `CHROMIUM_PATH` and `PRODUCT_TEST_ORIGIN` environment overrides.

The fixture uses a generated urban convenience store and a synthetic blue 16×16 PNG. The check starts
from the project screen, opens the fixture's stocked draft, selects a SKU, changes its name/price/promotion,
previews, saves, explicitly opens the child, and verifies the new inputs and unchanged original via API.
It checks ordinary wheel access to Save at 1280×900, 1280×640 and 390×844, including dialog clipping and
hit testing rather than merely checking viewport coordinates.

An initial viewport assertion failed because the test positioned the pointer during the dialog's resize
transition. Waiting for the 200 ms transition fixed the harness; no product CSS fix is claimed for this.
Both the diagnostic flow and the stricter clipping browser check completed successfully. That check
saved 13 changed placements, preserved the original and image links, and recorded zero page errors.
The new draft was `setup_products_85a01af2c086490cacef39f82fcca309` in isolated fixture data. Screenshots
and `browser-final.log` are under the execution log directory's `browser/` subdirectory. The temporary
API server was stopped after that verification; repository/user data was not used. A further browser
run injected one catalog HTTP 503, retried against the real API and verified the stale draft was replaced
before continuing through preview/save/reopen. It passed at the same three viewports, again saved 13
placements, preserved the original and image links, and reported zero page errors (`browser-recovery.log`,
draft `setup_products_629f60be496c4ec39f685b913fccc1c6`). Its temporary API server was also stopped.
That recovery script initially waited for a SKU that was outside the first 100 rows after reload reset
the search (catalog position 111). The script now waits for the explicit discard to finish, reapplies
search and checks the original name; this corrects the test harness, not product code.

## Limits and next candidate

- The UI entry is in the preparation dashboard for stocked drafts, not run playback. Catalog search shows
  100 rows at a time; saves change at most 500 exact SKUs. The model has no per-product category field.
- Unsaved inputs and the last 20 undo operations are local to the open dialog, not persisted drafts.
  An accepted save may finish after the dialog closes; inspect Layouts before starting a new request.
- A receipt reserved before a failed layout write deliberately requires checking Layouts and a new preview;
  it is never silently replayed into a replacement for a deleted/partially written draft.
- Save serialization covers this editor; other writers do not share its lock. Snapshot checks detect
  changes read before preparation; the editor always derives a child and never writes the source.
- No live model, actual store dataset, user interview, touch-device test or time-saving measurement was
  performed. Software-rendered desktop Chromium with a mobile viewport is not a physical mobile test.
- Next investigate filling **empty existing shelves with a reviewed starter assortment** while preserving
  existing products. Compare with current all-floor template/assortment behavior before choosing it; this
  targets onboarding and avoids another photo or analytical-module cycle.
