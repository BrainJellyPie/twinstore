# Keep workbook uploads ordered through preparation

The upload control only became busy during the final slot request. Two files
could overlap during file reading, image extraction or image uploading. With a
delayed first file, the second saved first and was then overwritten by the first.
Staged files also continued to slot replacement after unmount or layout changes.

A synchronous reservation now covers preparation through slot completion. The
control is busy throughout, releases on success/failure, and checks that its
layout scope is still mounted before starting slot replacement. Project/layout
changes remount the inner control so stale preparation and feedback are discarded.

Image batches now wait for all issued requests to settle before reporting a
failure. The former fail-fast Promise.all could release the upload reservation
while old image writes remained in flight. Existing best-effort behavior remains:
image failures do not prevent valid product rows from being imported.

## Verification

- Reproduced old save order [second file, first file] during reading, extraction
  and image uploads. All 8 initial component regressions failed in 2.13 seconds.
- Unmount, project/layout switches, malformed files, extraction failures, save
  failures and corrected-file retries; duplicate selections cannot bypass the
  reservation. The 57 focused component/workbook checks passed in 2.81 seconds.
- Additional image-batch fault injection: 4 failures before the fix, covering
  either request failing first and the delayed request succeeding or failing.
  Final component and image API checks: 28 passed in 2.39 seconds.
- TypeScript and targeted ESLint pass. Final production build: 16.61 seconds,
  with existing bundle-size and Babel timing warnings. No model calls.

Leaving a view prevents subsequent slot submission; it does not roll back image
or slot requests that the server has already accepted.
