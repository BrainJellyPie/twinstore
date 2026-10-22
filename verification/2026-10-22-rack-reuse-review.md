# Reuse shelf products — implementation and verification

Repository: `BrainJellyPie/twinstore`, branch `feat/operator-modules`, 2026-10-22 UTC.

## Selection and flow

See [candidate research](2026-10-22-rack-reuse-candidates.md) for the scenario, inspected public sources,
existing flows, alternatives and limitations of the requirements evidence. No interviews, timed usability
study or sales-effect study was conducted.

Step 2 now offers **Reuse shelf products**: choose an existing stocked shelf/fridge, search/select compatible
empty destinations, preview, save a child layout and explicitly open it. UI calls typed query/mutation
services and three routes; application snapshot/storage logic calls the pure engine/domain logic. It uses
existing SKU/image identities and no model or new spreadsheet. Original geometry and stocked racks are kept.
Unlike category-based starter filling, this copies the exact finished assortment, including order and levels.
No measured time saving or reduction in clicks is claimed.

## Remote integration cutoff

The second fetch at approximately 01:30 UTC found main `1de8953c` and AI UX `9422ba9b`. Both were
merged as `06c1aebb` and `37c94d39`, retaining operator work. Kept the DOM-observable layout-brief test
harness, routed-draft callback documentation, and both changelog sections. Incoming brief/shopper ownership
guards, boundary tests, release workflow and hypothesis/VLM changes are preserved. The interrupted frontend
run against the earlier integration is not counted as final validation. Destination branch is checked again
before the normal, non-forced push.

## Separate boundary review and repairs

After the initial API and UI workflow tests passed (one each), the boundary phase added real HTTP/storage,
geometry, UI lifecycle and browser checks. Covered:

- Empty/duplicate/self/unknown/overlong/null/boolean destinations, extra fields, bad snapshot/currency format,
  incompatible fixture, empty source, one/100/101 destination limits, Unicode IDs/names, zero prices,
  invalid/unsafe stored prices and exact value preservation.
- Locked/blocked/unreachable source or destination, already stocked target, malformed/overlapping layout,
  duplicate rack IDs, rotated multicell shape, absolute compass sides, extra empty slots, all-or-nothing
  batches, exactly 50,000 resulting placements and rejection above that limit.
- Changed products/geometry/currency, replay with different choices/source, busy save lock, lost response
  after a committed write, interrupted write reservation, later child edits, deleted child/source, retained
  building-floor context, and another source edit after the snapshot read. The child retains reviewed values
  while that later edit stays in the original. Identical retries preserve the child rather than duplicate it or undo newer edits.
- API failures/retry, hidden selection retention, cross-filter selection cap, pending-request edit locks,
  discarded previews after choice changes, stale source options, close/reopen/layout-switch with late saves,
  source selector accessible role, uncertain save replay after a currency refresh.

A newly added test used Playwright’s `exact` option with Testing Library, which TypeScript rejected;
removed that unsupported option (string role names already match exactly). This was test-code repair.

Two product bugs were reproduced and repaired with regression tests:

1. Refreshing options after preview could relabel old prices with a new currency and leave the old save
   action visible. A failing UI regression demonstrated it. Preview display/save now checks its snapshot;
   uncertain-save retry retains the original request identity and original currency.
2. SKU-manifest uploads normally leave persisted slot image URLs null. Browser inspection showed **no image**
   although the opened layout had the image. A failing API regression reproduced this. Preview now resolves
   existing project image links on a copy of the report; saved slot values and the original are unchanged.

The initial browser script's exact label lookup included nested select options and timed out. It was corrected
to use the selector's accessible `combobox` role; this was a harness issue, not counted as a product bug.
The supported classic renderer was used for the completed browser check to avoid software-GL load from
realistic rendering. Browser checks exercise actual UI/API/storage, not mocked routes, except deliberately
losing one save response *after* the actual API committed it.

## Execution evidence

Local logs and screenshots: `/workspace/.verification/twinstore-rack-reuse/` (not committed).
Reproducible scripts: [seed](rack-copy-browser-seed.py), [browser workflow](rack-copy-browser-check.mjs).
Tests live in `backend/tests/server/test_rack_copy_api.py` and
`frontend/src/features/products/__tests__/RackCopy.test.tsx`.

Final checks on the integrated code:

| Check | Actual result | Evidence |
| --- | --- | --- |
| Backend `uv run pyright src/` | 0 errors, 0 warnings | `pyright-final.log` |
| Backend `uv run pytest` | 15,547 passed, 1 skipped, 556.36s | `pytest-full.log` |
| Backend app import | `OK 222` routes | `boot-final.log` |
| Frontend pnpm 10.33.0 build | Passed, 23.92s Vite phase | `build-final.log` |
| Frontend pnpm 10.33.0 lint | 0 errors, existing 19 warnings | `lint-final.log` |
| Frontend `pnpm test --maxWorkers=1 --reporter=verbose` | 3,652 passed, 199 files, 476.66s | `frontend-full.log` |
| Integrated browser workflow | Passed, 3 viewports, 0 page errors | `browser-integrated.log` |

The browser check covers Step 2 entry → source/destinations → preview → save with a lost response → retry →
open saved child → verify in bulk product editor and real API. It checks exact prices/order/levels/SKU images
and the unchanged original at 1280×900, 1280×640 and 390×844; mobile screenshot was inspected.
Build retains bundle-size/plugin-timing notices. Unit tests emit non-fatal missing-RouterProvider warnings
from integrated run-analyst recovery fixtures; no browser page error was observed.

The one skip is the opt-in Grounding DINO rendered-facings test, which requires the capture extra,
`PARASTORE_TEST_GDINO=1` and an approximately 700MB model download. No new test was skipped. The new module
has 41 API tests and 12 UI tests, all included in the completed full suites above.

An earlier full backend run was
intentionally stopped after 9,868 passed / 1 skipped to incorporate the newly found image preview bug;
that partial run is **not** treated as full-suite validation.

## Scope and next candidate

Synthetic local fixtures only; no actual store data, live model, full simulation, sales lift or stock inference.
Browser checks use a small fixture; maximum-size browser rendering has not been load-tested. Placement limits
were exercised through the real API/storage/geometry pipeline.
Maximum 100 destinations; matching fixture and rotated footprint only; no rotation/mirroring of assortment,
no replacement of stocked racks, no silent partial copy. Products may still carry illustrative starter values.
Image identities/links are shared; later image replacement/deletion can change the appearance of both layouts.
The copy snapshot covers layout/currency, not independent image-file revisions. Choices are transient until
saved; a deleted child or interrupted reservation requires a new explicit preview after checking Layouts.

Next candidate from a different convenience flow: review-and-match multiple uploaded images to existing SKUs,
with explicit handling of uncertain matches. Investigate the existing ProductLibrary multi-upload before
implementing; do not duplicate its current upload/cutout support.
