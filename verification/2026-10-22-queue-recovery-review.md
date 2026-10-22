# Photo queue recovery: implementation and verification

2026-10-22 UTC. Repository `BrainJellyPie/twinstore`, branch `feat/operator-modules`.
This extends the existing Capture intake, review, crop registration and combined-layout workflow.

## Selection and integration

The [candidate comparison](2026-10-22-queue-recovery-candidates.md) records the operator interruption
scenario, marketer/researcher uses, public sources and other convenience candidates. These are requirements
hypotheses based on code and documentation, not user interviews, market validation or measured time savings.
The previous cycle filled empty shelves; this cycle preserves photo preparation across a browser restart.

Started from clean operator `e602be2e`. Integrated main `3970ff65` as `5c354cf3` and AI UX `c0840349` as
`98c4d720`. Preserved operator starter/product-editing work and incoming draft ownership guards. Town routing
uses the incoming request-text queue; marketing keeps consumed-prefill tracking while adding concept/shelf
destinations. Scenarios `692d80ba` and photoreal `dc9a7805` were already ancestors. No force push, branch
removal or change to the previous parastore working directory is involved.

The pre-push fetch found main `6e1970d1` and AI UX `052af553`; operator remained `e602be2e`.
Integrated them as `e4a5a192` / `04f3400f` before final validation. Kept main's newer concept form/context
ownership checks, minor-unit price validation and unambiguous image matching, plus starter editability/mobile
fixes. Kept AI UX's layout-in-words and design-brief options. Conflicts in routed-prefill consumption were
semantically equivalent; kept one callback and both concept/shelf tests. Changelog retains all workflows.
The natural-language candidate is consequently partly covered by incoming work, not claimed as this cycle's
new feature. Final checks run on this integrated snapshot.

## User flow and implementation

Capture → choose photos/settings → **Save queue on this browser** explicitly retains the original bytes,
names, SHA-256 digests, stable upload request IDs and settings in IndexedDB. Save/restore makes no model call.
On returning, **Continue saved photo queue** exposes recovery even when an accepted capture opens by default.
**Restore saved queue** validates all bytes before replacing local choices and leaves the queue paused.
**Start / resume queue** replays the existing idempotent capture API: previously accepted requests return their
capture, while unaccepted requests create new captures. Photo bytes are retransmitted during replay; this
is capture/job deduplication, not a bandwidth-saving claim. Recognition status is recovered from the server.

When recovery is enabled, changed intent is stored before the next upload, including IDs for intentional new
recognition attempts. Unchanged intent checks its revision without rewriting photo blobs. A readwrite
transaction compares revisions before replacement/deletion; competing tabs cannot overwrite each other's
saved copy. **Replace local queue from saved copy** resolves a stale local copy explicitly. **Forget saved
copy** keeps live files and server captures. **Clear queue and saved copy** removes storage before local files;
storage errors leave both intact. Paused changes need an explicit Save before leaving.

No new backend or analysis API is introduced. The existing capture API, byte deduplication and sequential
recognition remain in use. `fake-indexeddb@6.2.6` is a pinned development-only test dependency.

## Separate boundary-test and repair phase

Basic existing queue tests passed (14 tests), followed by two new storage/UI happy-path tests. The expanded
boundary suite then reproduced these failures before repair:

| Reproduced problem | Repair and regression evidence |
| --- | --- |
| A quota DOMException crossing a test/browser realm displayed a generic error | Read the error's name/message, explicitly explain full browser storage. Initial boundary run: 2 failures / 35 passes; repaired run: 51 passes including existing queue tests |
| A changed saved revision blocked resume, while existing local files also disabled Restore; Clear/Forget conflicted too | Allow explicit replacement from the latest copy. Validate files and revision before replacing local state; stale-revision UI regression now resumes the winning list |
| Synchronously thrown storage exceptions that are not Error instances were still reduced to a generic message inside the transaction | Preserve the actionable message at the transaction boundary. Separate regression: 1 failure / 29 passes before repair; final focused capture/routing run passes |
| Integrated concept/shelf routes redrafted after switching tabs and returning | Consume routed prefill once in both new builders and gate delivery on loaded context. Reproduced 2 failures / 14 passes; regression now passes for tab switches, layout changes and a subsequent explicit request |

The final merge added two concept-loading tests whose mock rationale differed from this branch's shared
fixture. The first integrated full frontend run completed with 2 failures / 3,389 passes (503.53 s), both
matching this fixture-text mismatch. Unified the expected rationale without weakening API call-count or
context-loading assertions; the focused routed-draft/brief set then passed all 19 tests. The incoming brief
test also assigned to a global variable during render; it now asserts rendered state through a test output,
removing the new compiler warning without changing application code. Full frontend tests were rerun.

The initial build also found an ES2022-only `.at()` in a new test while this repository targets ES2020.
Replaced it with indexed access; no application compatibility setting was changed.

Coverage includes empty inputs, exact 20-file and 100-MiB storage limits, per-file overflow, duplicate IDs and
content, malformed schema/options/metadata, negative/fractional/nonfinite timestamps, Unicode filenames,
changed photo bytes, missing storage support, quota/clone/abort failures, competing writes and stale deletion,
a late initial read, pause/unmount during checkpoint, failed clear/forget, unavailable saved models, changed
project currency, and saving new retry IDs before any upload. Existing tests cover upload/poll failure,
recognition retries, file formats, duplicate names, drag-and-drop and combined-layout save conflicts.
There is no new numeric estimator or export API; price rounding/exports are outside this feature. Maximum-size
storage tests exercise real blobs; they do not claim a 100-MiB browser performance benchmark.

## Browser integration protocol

The [fixture generator](capture-queue-browser-seed.py) creates two synthetic shelf scenes and a byte-identical
duplicate. It refuses an existing `.data` directory. Run it in a fresh disposable directory using the backend
Python environment and `PYTHONPATH=/absolute/path/to/twinstore/backend/src`. Build the frontend, then run
`uvicorn store_emulator.server.main:app --host 127.0.0.1 --port 18769` from that fixture directory with
`TWINSTORE_LOCAL_VLM_AUTO=0`. Run [the browser check](queue-recovery-browser-check.mjs) from the same directory.
`PLAYWRIGHT_MODULE` supplies the Playwright installation; `CHROMIUM_PATH` defaults to `/usr/bin/chromium` and
`CAPTURE_TEST_ORIGIN` overrides the localhost origin. Each run uses its own persistent browser profile.

The check saves the queue using real IndexedDB, uploads with classic geometry detection and no VLM, discards
the first successful API response, closes Chromium entirely and relaunches the same profile. It restores
without reselecting files or uploading automatically, resumes the accepted request without duplication,
reviews both photos through the editor, saves explicit synthetic names/prices, combines crops/products into
a child layout, opens it, and compares the untouched base store. It also checks review reachability using
ordinary scrolling at 1280×900, 1280×640 and 390×844 and checks for uncaught page errors.

The completed Chromium run (`browser-second.log`) passed: one accepted capture before restart, exactly two
after Resume, no file reselection, two reviewed products/four facings on two new racks with crop URLs, unchanged
base store and zero page errors. The first harness attempt (`browser-first.log`) used `route.fetch()`, which
omitted Chromium's multipart image bytes and got 422; no capture was accepted. The check now intercepts at
CDP's **response** stage so the original browser multipart request reaches the API intact. That was a test
harness defect, not evidence of an application upload failure. The recovery flow itself needed no browser
fix after unit-boundary repairs. All images/names/prices in this check are synthetic fixtures or explicit edits.

## Executed validation

Local logs, synthetic data and browser profiles are under
`/workspace/.verification/twinstore-queue-recovery/`, outside normal backend data and outside Git.
The first full backend/frontend runs were interrupted by an exec-server transport disconnect (the logs
end without a test summary; their processes became defunct). They are not counted as passing results.
Environment status recovered; final full checks were restarted after the additional integrations. The
completed browser check preceded these merges; `git diff 160bbf85 04f3400f -- frontend/src/features/capture
frontend/src/services/mutations/captureUpload.ts frontend/src/services/queries/captureUpload.ts
backend/src/store_emulator/application/capture* backend/src/store_emulator/server/routes/capture.py`
shows no change to the recovery/upload workflow. Final full suites cover the integrated application.

| Check | Completed result |
| --- | --- |
| Backend `uv run pyright src/` | 0 errors, 0 warnings after final integration (`backend-pyright-final.log`) |
| Backend `uv run pytest` | 15,221 passed, 1 skipped, 648.32 s (`backend-pytest-final.log`); exit 0. Skip: existing opt-in Grounding DINO test needing capture extras and ~700 MB model download |
| Backend app import smoke | `OK`, exit 0 after final integration (`backend-boot-final.log`) |
| Frontend build, pinned pnpm 10.33.0 | TypeScript/Vite pass, Vite 26.48 s (`build-verified.log`); existing large-chunk/plugin-timing notices |
| Frontend lint, pinned pnpm 10.33.0 | 0 errors, existing 19 warnings (`lint-verified.log`). The first integration run had one additional warning from AI UX `052af553` in `LayoutBriefField.test.tsx`; repaired its test harness and reran lint. No warning in recovery code/tests |
| Frontend full tests, pinned pnpm 10.33.0 | 3,391 passed in 188 files, 388.60 s (`frontend-test-serial.log`); exit 0 after all integration/test repairs |
| Focused capture and routed draft tests | 148 passed in 14 files, 38.13 s (`queue-final.log`) after recovery repairs; before final remote integration |
| Real Chromium / FastAPI / classic detector | Passed browser restart, accepted-response loss, duplicate prevention, photo review, product/crop/layout save, base preservation and three viewport sizes (`browser-second.log`) |

Frontend commands use `npm exec --yes --package=pnpm@10.33.0 -- pnpm <build|lint|test>`;
full frontend tests use `test --maxWorkers=1`. An intermediate two-worker run reported three failures in
existing `TemplatePicker` priority tests (two reached about five seconds); it was stopped and rerun serially
with no backend/browser/build work running. These same tests passed in the first serial full run. No test
assertion or timeout was relaxed, and no lint rule was disabled. The intermediate parallel run is not counted
as passing verification. The final serial run passed all 3,391 tests, including the three priority cases.
Browser testing uses synthetic scenes and no live VLM.

A destination-only pre-push fetch again confirmed `origin/feat/operator-modules` at `e602be2e` is an ancestor
of this branch. The normal push preserves that history. Feature implementation is `160bbf85`; later merge
and verification commits preserve the additional remote work and document the final tested state.

## Limits and next candidate

Recovery is browser/site-local and opt-in; quotas, private mode, eviction and clearing site data can remove it.
It is not a cloud backup or cross-device sync. Copies intentionally store intent rather than progress. The
existing single-worker capture service and durable request receipts handle replay; this is not a distributed
job system. A definitively failed recognition still requires an explicit new attempt. A removed accepted
capture returns a conflict rather than being recreated. Unreadable future-version copies remain unchanged;
site-data controls can remove them. Saved-model availability is not guaranteed after restart. A saved
**App's vision model** selection still refers to the configured default at upload time; it does not pin a
provider/model version. Explicit model selections and the no-model choice retain their original identifiers.

No live VLM, real store photos/inventory/prices, recognition accuracy study, shopper simulation or user timing
study was run. Synthetic names/prices are explicit test corrections. Existing photo-to-grid approximations
and reduced-facing consent remain; exact physical dimensions/stock quantities are not inferred.

Next different-flow candidate: reuse a stocked rack in another location with a preview of capacity/rotation,
or assign product-library images to several SKUs at once with explicit ambiguous-match review.
