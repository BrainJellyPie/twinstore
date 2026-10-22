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
  building-floor context. Identical retries preserve the child rather than duplicate it or undo newer edits.
- API failures/retry, hidden selection retention, cross-filter selection cap, pending-request edit locks,
  discarded previews after choice changes, stale source options, close/reopen/layout-switch with late saves,
  source selector accessible role, uncertain save replay after a currency refresh.

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

Final mandatory validation results are recorded below after completion. An earlier full backend run was
intentionally stopped after 9,868 passed / 1 skipped to incorporate the newly found image preview bug;
that partial run is **not** treated as full-suite validation.

## Scope and next candidate

Synthetic local fixtures only; no actual store data, live model, full simulation, sales lift or stock inference.
Maximum 100 destinations; matching fixture and rotated footprint only; no rotation/mirroring of assortment,
no replacement of stocked racks, no silent partial copy. Products may still carry illustrative starter values.
Image identities/links are shared; later image replacement/deletion can change the appearance of both layouts.
The copy snapshot covers layout/currency, not independent image-file revisions. Choices are transient until
saved; a deleted child or interrupted reservation requires a new explicit preview after checking Layouts.

Next candidate from a different convenience flow: review-and-match multiple uploaded images to existing SKUs,
with explicit handling of uncertain matches. Investigate the existing ProductLibrary multi-upload before
implementing; do not duplicate its current upload/cutout support.
