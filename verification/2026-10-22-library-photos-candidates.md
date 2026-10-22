# Convenience cycle: reuse uploaded product photos

## Baseline and user scenario

Repository: BrainJellyPie/twinstore, feat/operator-modules. Started clean at 04821954;
merged main 5b5451e4 as a0192b72 and AI UX 3646ffc9 as 039047b6. README organization
from AI UX retained with operator reuse/recovery guides. Existing operator features remain.

A store operator has stocked a template and uploaded packshots under Market → Products.
A marketer wants the same packshots on the actual shelf before reviewing a layout; a researcher
needs a separate variant preserving the original. ProductLibrary already uploads multiple files,
reads packs optionally, and links package metadata to SKUs. Those links feed marketing variants,
not SlotItem images. Step 2 currently has no way to reuse these images; Excel image import is a
separate route to a project-wide image manifest. Adding another upload/recognition queue would duplicate work.

These are source-based requirements hypotheses, not interviews, measured task times or market validation.

## Compared candidates

| Candidate / users | Required input and actions | Evidence / existing gap | Data, feasibility and verification |
| --- | --- | --- | --- |
| **Selected: reuse library photos on placed products** / operators, marketers, researchers | Existing layout + uploaded photos; review suggested links or choose SKU/photos; preview; save/open variant | ProductLibrary links do not populate store images. Shopify documents selecting existing product media and separate variant assignment; NN/g recognition/control; WCAG review/correct before storage | No new model; deterministic SKU links only, ambiguous links need choice. Snapshot photos and layout revision; API and browser verify images, prices, order and original preservation |
| Upload packshots with filename-to-SKU matching / operators | New files, review filename suggestions, apply | Useful first-import route, but existing ProductDrop already has multi-file input and model-assisted linking | MIME/size/duplicates, partial failure and retry require another bounded queue; defer until existing assets can be applied end to end |
| Restore unfinished product edits / researchers/operators | Opt-in browser draft, restore/correct | Capture queue already has recovery; product edits do not | IndexedDB revision/migration/stale-layout work; test reload, eviction, conflicting tabs; next different task-continuity candidate |
| Bulk edit fixture names / operators | Select fixtures, enter prefix/numbering, preview | Helps large template navigation, but doesn't finish product appearance | No model; collision/Unicode/undo tests; lower priority than broken photo-to-shelf connection |

## Public sources checked 2026-10-22

- https://help.shopify.com/en/manual/products/product-media/add-media — add media from product details,
  select existing files and assign images to variants. Retrieved successfully; local evidence in
  /workspace/.verification/twinstore-library-photos/shopify-add-media.{html,txt}.
- https://www.nngroup.com/articles/ten-usability-heuristics/ — user control/freedom, recognition rather
  than recall, error prevention. Retrieved HTML/text beside above.
- https://www.w3.org/WAI/WCAG22/Understanding/error-prevention-legal-financial-data.html — check/review,
  correct or reverse changes to stored user data. Design guidance, not a claim of WCAG conformance.

## Scope selected before implementation

Step 2 → Use library photos: search placed products, optionally suggest only unique existing SKU links,
review current/proposed photos, opt in to replacement, save a separate child layout, open it. Existing
Market upload remains the entry for new images; do not re-upload or call a model. Preserve prices, quantities,
geometry, source layout and source photos. Copy selected image bytes into immutable project snapshots so
later library deletion cannot break saved images. Bounded selection (100 SKUs), source/asset revision checks,
retry identity, no cross-project assets, no guessed name/price/stock. This is image assignment, not photo
planogram reconstruction. Separate boundary phase follows initial working implementation/tests.
