# Stable artwork across vision optimization candidates

Vision optimization constructed a live project image loader when its worker began.
Package deletion and SKU replacement could change a queued job's input or a shelf
not yet rendered during judging. Adding a new photo before worker startup also
changed an accepted job's appearance.

Startup now snapshots product images under its existing project tree/setup guards,
before registering pending status or submitting the worker. The captured loader is
shared across calibration and candidate judging. Rule-only optimization does not
copy artwork. A failed copy/status registration removes the new job directory.
Direct legacy calls to the worker without a captured loader keep their prior fallback.

Focused checks used temporary files and fake vision providers:

- Before: six failures and two passes in 3.50 seconds. Mutations cover deleted
  packages, replaced SKU photos and newly added art, while queued or judging. The
  existing loader already retains absence when its manifest was loaded before a
  new SKU photo appeared; that one boundary already passed.
- After: ten passes in 19.07 seconds, including all eight new image/failure/rule
  exclusion checks and both existing optimization API end-to-end tests.
- Strict Pyright for the changed application module: zero errors or warnings.

The shared snapshot helper's prior tests cover bounded-cache eviction and distinct
artwork on separate placements of the same SKU.
