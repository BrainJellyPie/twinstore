# Stable product artwork for vision simulations

Ordinary vision runs loaded project artwork lazily after being queued. Deleting a
package, overwriting a SKU photo, or adding previously absent artwork changed what
later shelves/customers saw within the accepted run. Previews had the same problem.

The start endpoint now freezes product images for the effective vision engine before
publishing pending status. It uses the existing decoded-image snapshot implementation,
under the project tree, setup and run-ID locks. Rule starts retain their independent
run-ID locking and do not copy artwork. Copy failure cleans its partial snapshot
before the setup or run becomes active.

The worker reopens a validated manifest from `input/images`. An explicit status flag
prevents silently falling back to current project artwork when the saved manifest or
folder disappears. Snapshots include absent artwork, preserve distinct art for the
same SKU, and read only their own saved PNGs after bounded-cache eviction. Existing
direct/legacy worker calls without that flag retain their prior loader behavior.

Validation used fake vision entry points and local rule simulations:

- After correcting the initial test URL to the actual `/runs` route, the baseline
  had 14 failures and one pass in 3.61 seconds: three source mutations, queued versus
  running changes, normal versus preview mode, and failed-copy cleanup.
- An intermediate run exposed four test fixture mismatches: it requested the raw
  item rather than the accepted store item whose image URL the setup API hydrates.
  The tests now inspect the actual store item handed to the simulation.
- Final targeted run: 49 passes in 33.11 seconds, including 17 image/lost-snapshot
  cases and 32 concurrent run-ID cases with rule and vision starts.
- Restoring a snapshot after deleting 131 source images, retaining distinct art for
  one SKU and surviving cache eviction passed. Related marketing image and editor/
  simulation state checks also passed during focused development.
- Strict Pyright for all three changed modules: zero errors or warnings.

This change freezes product artwork. Separately rendered 3D shelf photographs and
vision optimization jobs remain separate paths under investigation.
