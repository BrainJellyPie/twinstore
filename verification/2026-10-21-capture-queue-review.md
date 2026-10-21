# Multi-photo capture intake: implementation and verification

2026-10-21 UTC. Repository: `BrainJellyPie/twinstore`, branch `feat/operator-modules`.
This extends Capture's existing recognition, product correction and combined-layout workflow.
It does not add an analysis worksheet or claim observed sales, inventory, prices or recognition accuracy.

## Selection and integration

See [candidate comparison](2026-10-21-capture-queue-candidates.md) for the concrete six-photo scenario,
public sources, alternatives and data requirements. These are source-based requirements hypotheses;
there were no user interviews, usability timing measurements or market validation.

The previous uploader read only `files[0]` and immediately switched into its editor. Users can now choose
or drop multiple images once, inspect individual file rejections and explicitly start a controlled queue.
One photo reaches a terminal recognition state before the next is uploaded. Review opens the existing
editor; the previous cycle's combination flow saves reviewed products, crops and racks into a new draft.
No measured time-saving claim is made.

Preserved operator head `4aab7dba` and integrated main `ab76a1ee`, scenarios `692d80ba` and edge-case loop
`db41a09a`. Before full verification, also integrated main `c964e125`, edge-case loop `a3336975` and AI UX
`99f48a20` (integration head `bde716ae`). An append-only conflict in `AddLayoutDialog.test.tsx` was resolved
by retaining both the background creation/input-preservation and empty-project recovery tests.
No force push, branch deletion or parastore-directory changes were made.

A subsequent fetch found AI UX `4e8f9df0`, which changes interview follow-up generation and model-error
messages rather than photo intake. It is a candidate for the next integration cycle; it is not claimed
as part of this verified snapshot. The operator destination remained `4aab7dba` at that check.

The pre-push fetch then found main/edge-case head `dba89df7`, adding route-error recovery and localized
retry controls. Integrated as `d4806657`. The earlier append-only test conflict reappeared because both
branches placed the same empty-project test at different locations; retained the already reviewed
combined file, with each test present once. The effective merge changes only three frontend files.
`git diff --exit-code bde716ae d4806657 -- backend` confirmed no backend change. Frontend build, lint and
full tests were rerun after this integration; backend results apply to identical backend source/tests.

## Scope and boundaries

- Up to 20 local files; each at most 25 MiB and aggregate at most 100 MiB. JPEG/PNG/WebP only.
  Byte hashing skips identical files even when renamed; different bytes with the same name remain separate.
- Shared settings and currency stay fixed until the local list is cleared. Project currency must load
  before selection; HTTPS or localhost is needed for browser cryptography.
- Pause stops future uploads, not the accepted server job. Removing/clearing the local list does not delete
  server captures. Unmount aborts pending client requests and prevents later uploads/callbacks.
- Optional multipart request IDs deduplicate uncertain upload retries. Reusing an ID with changed input
  returns 409. Poll failures resume polling without resubmission. Definitive recognition failure requires
  an explicit new attempt with a new ID. One uncertain request blocks new attempts elsewhere in this queue.
- Receipts outside deletable capture directories prevent a retry from resurrecting a removed photo.
  Rejected executor submissions are marked failed; single-worker startup marks interrupted jobs failed.

## Separate boundary-test and bug-fix phase

Basic checks first passed: one real classic-detector API workflow (5.37 s) and one sequential queue UI
workflow (2.80 s). Broader tests were then added and the following failures reproduced and fixed:

| Reproduced failure | Repair and regression evidence |
| --- | --- |
| Retrying an accepted photo after deleting it created another capture/job | Persistent request receipt outside the removable capture folder; API retry now returns 409 |
| Executor rejection raised an unhandled RuntimeError and left pending state | Write a failed terminal status and return 503; isolated failing test reproduced before the repair |
| A project metadata refresh changed the currency of already queued files | Freeze currency when the first valid file enters the queue; USD-to-KRW refetch regression went from failed to passed |
| Navigation tests still exposed inactive upload controls in jsdom when hiding depended on CSS classes | Native `hidden` wrapper makes the inactive state explicit; navigation/loading regression coverage. This was not a measured screen-reader failure in a real browser |
| Retrying an earlier failed recognition bypassed a later photo's unknown status | Disable new recognition attempts until the uncertain upload/poll is resolved, and guard queue execution; focused run changed from 1 failed / 11 passed to 12 passed |
| At 1280×900 the final Review button extended below the viewport and ordinary wheel scrolling could not reach it | Size the queue to the remaining desktop flex space; real Chromium regression initially failed, then passed with the entire control visible |

The first boundary backend run reported 2 failures / 13 passes. The initial executor failure also exposed
a test-isolation issue: the fixture did not await submitted work before restoring its temporary working
directory. The fixture now waits for its futures; the executor defect was reproduced independently before
fixing it. No contaminated run is used as proof of product correctness.

Additional boundaries cover empty/corrupt/oversized server payloads, request IDs of incorrect length/case
and traversal-like input, changed currency/rack/model, concurrent replay, Unicode names, restart recovery,
zero and exact-limit file sizes, unsupported MIME/extension, 21-file selection, aggregate limits, duplicate
content and duplicate names, pause/resume, removing an unsent file, late responses after unmount, failed
project lookup/retry, multi-file drag-and-drop and explicit new recognition attempts. Large-file UI budget
tests use controlled File size metadata; the backend test sends an actual payload beyond 25 MiB.
This module adds no price arithmetic or export endpoint. Prior combined-layout tests cover stale previews,
rounding/missing prices, idempotent saves and placement limits and were rerun in the focused backend set.

## End-to-end browser verification

The committed [fixture generator](capture-queue-browser-seed.py) refuses an existing `.data` directory.
Run it by absolute path in a fresh disposable directory with the backend environment and
`PYTHONPATH=/absolute/path/to/twinstore/backend/src`, then
start `uvicorn store_emulator.server.main:app --host 127.0.0.1 --port 18766` from that directory with
`TWINSTORE_LOCAL_VLM_AUTO=0`. Build the frontend first. The
[Playwright script](capture-queue-browser-check.mjs) uses Chromium (`CHROMIUM_PATH`, default
`/usr/bin/chromium`) and `PLAYWRIGHT_MODULE` to locate a Playwright installation. Run the script from the
same fixture directory. `CAPTURE_TEST_ORIGIN` can override the localhost origin.

The script selects two distinct generated shelf scenes and a byte-identical duplicate, explicitly starts
classic detection with no VLM, waits for both results, reaches review controls by wheel scrolling, corrects
each to one explicit test product priced at 1.99, saves the edits, combines both into a draft, opens that
layout and checks its API representation contains both products and crop image URLs. Product names/prices
are test inputs, not recognition claims. It also exercises short desktop and mobile queue scrolling and
checks for uncaught browser errors. Synthetic fixtures do not validate real shelf recognition.

## Required checks

Logs are local artifacts under
`/workspace/.verification/twinstore-capture-queue/`; synthetic application data is isolated under its
`browser/` directory, not the repository's normal backend data folder.

| Check | Executed result |
| --- | --- |
| Backend `uv run pyright src/` | 0 errors, 0 warnings |
| Backend `uv run python -c "from store_emulator.server.main import app; print('OK')"` | `OK`, exit 0 |
| Backend `uv run pytest --basetemp=/workspace/.verification/twinstore-capture-queue/pytest-full` | 14,861 passed, 1 skipped, 620.25 s. The skip is the existing opt-in Grounding DINO test requiring capture extras and a ~700 MB download |
| Frontend build via pinned `pnpm@10.33.0` | TypeScript and Vite passed after final integration; Vite 18.84 s. Existing chunk-size/plugin-timing notices |
| Frontend lint via pinned `pnpm@10.33.0` | 0 errors, existing 19 warnings; no warning in the new queue files |
| Frontend full tests via pinned `pnpm@10.33.0` | 2,923 passed in 154 files, 143.85 s, after final integration |
| Focused backend capture, upload queue and combined-layout tests | 42 passed, 22.47 s |
| Focused UI queue/file/navigation/loading tests after fixes | 29 passed in 4 files, 12.84 s |
| Real Chromium + FastAPI + classic detector | Passed; two reviewed products, four placed facings on two racks, crop URLs present, no browser page errors. Review controls reachable at 1280×900, 1280×640 and 390×844 |

Frontend commands used `npm exec --yes --package=pnpm@10.33.0 -- pnpm <build|lint|test>`.
The full frontend test run was isolated from backend tests, builds and the browser fixture server.
Before the final route-only merge it passed 2,910 tests in 153 files (137.78 s); the table records the
post-merge result. The browser workflow passed before that merge, which leaves the photo queue unchanged.
The final browser log is `browser/browser-final.log`; the intentional initial scroll failure is
`browser/browser-first.log`. Screenshots and all generated data remain local, not committed as real data.
Immediately before committing the final fixes, a destination-only fetch confirmed operator head
`4aab7dba` was still an ancestor of the local branch; the normal push preserves its history.

## Remaining limitations and next candidate

Local File objects are not durable across reload or project navigation. Accepted captures remain in
history; keep the Capture page open for unsent files. A server write interrupted after reserving an ID
but before creating a readable status requires selecting the file again for an intentional new attempt.
Receipts remain on disk. Recovery assumes the existing single-worker deployment; it is not a distributed
job queue. Other clients can submit their own jobs, so sequencing is per local queue, not a global model
concurrency limit. Deduplication is exact bytes within the local queue, not visual similarity across history.

No live VLM, real store photos, accuracy study, full shopper simulation or measured time-saving experiment
was run. Photo-to-grid mapping retains the existing approximation; this does not recover exact shelf
dimensions or physical stock quantities. Typical prices and missing names still require review.

Next different-workflow candidate: bulk product name/category/price edits with an affected-item preview,
preservation of unselected products and undo, using existing store data rather than asking for new CSVs.
