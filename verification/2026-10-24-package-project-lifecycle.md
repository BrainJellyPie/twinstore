# Keep package assets consistent with project deletion

Package upload checked the project before image processing but saved later without the
project tree guard. Deleting during resize could be followed by a successful upload that
recreated the deleted folder. Metadata writes and package-lock acquisition had the same
race, including an orphaned JSON file after a deleted PNG caused the response to fail.

Image preparation stays outside the transaction. Final PNG/metadata writes now recheck the
project under the shared tree guard. Package edit/read/delete guards acquire that tree lock
before the existing asset lock. Vision reads capture image pixels together with metadata,
release locks during provider work, then recheck the project/asset before the final write.
An unreadable saved image returns a client error before creating a provider request.

- Baseline lifecycle regression: 11 failed, 1 passed in 3.45 seconds.
- Focused lifecycle, existing package-read conflicts/API and photo validation: 39 passed
  in 5.72 seconds; strict Pyright zero errors/warnings.
- Additional corrupt-image client-error/no-provider check: one test passed (see test log).
- Races cover deletion first, final metadata commit first, package-lock construction,
  upload resizing, and deletion while the model answers. Slow model work stays unlocked;
  a deletion after the input snapshot can correctly make the final read return 404.
- Existing same-asset concurrency conflicts, older/newer model answers, manual links,
  ambiguous product names, image orientations and pixel-limit handling still pass.

No live provider calls, frontend changes or full suite. Other layouts' source changes are
outside this lifecycle fix; it preserves the existing exact-name product-linking behavior.
