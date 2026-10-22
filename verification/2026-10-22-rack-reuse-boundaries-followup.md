# Shelf reuse integration and independent boundary checks

Integrated `04821954` with the AI draft fixes from `6f83ad39`. Kept the current
layout-brief and marketing request-ownership regressions when resolving conflicts.
The existing shelf-reuse implementation passed the additional checks; no behavior
change was needed in the copy engine or dialog.

## Added regression coverage

- 224 geometry/copy cases: six footprints, four rotations, shelf/fridge fixtures,
  all four levels, and every pairing of copied/locked sides. Enclosed inaccessible
  faces remain unstocked. Destinations use the same world footprint even when their
  rotation metadata differs. Child edits cannot mutate siblings or the source.
- 21 HTTP cases: eight currencies, distinct placement values sharing one SKU,
  zero and maximum safe integer prices, recovery after source contents disappear,
  failures before/after receipt and child writes, and malformed request identities.
- 16 UI cases: pending previews across close/layout/project changes; snapshot,
  currency and query-error invalidation; uncertain-save replay after source lookup
  fails; exact safe-integer price display in six currencies.

Focused backend: **286 passed**. Focused product frontend: **56 passed**.
Strict backend types: zero errors. Server import smoke: OK.
Frontend build passed; lint retained the existing 19 warnings and zero errors.
Full frontend: **3,744 passed, 202 files** (233.30 seconds).
Full backend: **16,625 passed, 1 skipped** (556.21 seconds).

## Browser/storage check

An isolated synthetic project used the real API, storage, image manifest and built
frontend. No model or external API was called.

- Tested 320×568, 375×812, 812×375 and 1440×1000. The dialog had no horizontal
  overflow; real wheel input reached the save control in each viewport.
- Copied three placements to each of two empty shelves; rejected source/fridge
  selection; checked levels, product order, prices, regular prices and image links.
- Dropped the response after the server accepted a save. Retrying sent exactly
  the same request and recovered one child layout, without a duplicate.
- Explicitly opened the copy and verified the existing bulk product editor read
  its values. All 30 pre-existing JSON files retained their exact hashes.

An initial browser harness failure used stale coordinates returned by the browser
protocol after viewport changes. Reading the live DOM rectangle fixed the test;
no product change was made for that failure.
