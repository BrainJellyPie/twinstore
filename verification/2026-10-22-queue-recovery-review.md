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
Results are filled in only after the checks finish.

## Limits and next candidate

Recovery is browser/site-local and opt-in; quotas, private mode, eviction and clearing site data can remove it.
It is not a cloud backup or cross-device sync. Copies intentionally store intent rather than progress. The
existing single-worker capture service and durable request receipts handle replay; this is not a distributed
job system. A definitively failed recognition still requires an explicit new attempt. A removed accepted
capture returns a conflict rather than being recreated. Unreadable future-version copies remain unchanged;
site-data controls can remove them. Saved-model availability is not guaranteed after restart.

No live VLM, real store photos/inventory/prices, recognition accuracy study, shopper simulation or user timing
study was run. Synthetic names/prices are explicit test corrections. Existing photo-to-grid approximations
and reduced-facing consent remain; exact physical dimensions/stock quantities are not inferred.

Next different-flow candidate: reuse a stocked rack in another location with a preview of capacity/rotation,
or assign product-library images to several SKUs at once with explicit ambiguous-match review.
