# Online design chat integration and CPU probes

Integrated `claude/online-shopping-features-ji7y0f` at
`8c9fe039f59b640e2f902eaf6fabd85de715c69a`, on top of concurrent main
`ee35081f66c90be2b9be0dca2dd165a9eb7c917b` (the v0.6.0 integration).
The feature edits an unsaved shop design through chat, previews it, supports undo,
and creates a variant for a comparison run.
Preserved the subsequent conversation retention, debounced preview, marketing
package variants and narrow-screen improvements. Resolved three overlapping
frontend edits and rechecked the merged behavior before publication.

## Actual local inference

Qwen3.5-0.8B Q4_K_M, llama.cpp b11878, CPU only, five threads, 8,192-token
context, one slot. The production LiteLLM/Instructor client used JSON Schema,
temperature 0.2, seed 0 and the application's 900-token response limit. All runs
used a fresh cache. These text requests used the same running VLM that was used
for the preceding package-image probes; no replies were mocked.

The original nullable, full-options response caused unintended edits even when
the owner asked for one change. The new wire response is a list of typed
`{option, value}` updates. Canonical changes and cache records retain the existing
flat representation. Known options, per-option types and limits, uniqueness and
non-null values are validated before applying changes.

| Request | Original observed result | Accepted implementation, fresh run |
| --- | --- | --- |
| Korean: change only the theme colour | Changed colour and page style; 2 calls, 18.21 s | Only colour; 1 call, 4.20 s |
| Free delivery and remove the welcome popup | Changed style and delivery but retained the popup; 1 call, 9.41 s | Only delivery and popup; 1 call, 4.62 s |
| Change only the style to neon | Also changed colour, popup and load time; 1 call, 5.25 s | Only page style; 1 call, 3.07 s |

Timing is an observation on this CPU, not a performance guarantee. Prompts and raw
responses are retained under `/workspace/scratch/cpu-vlm-probe/`. The accepted
production runs are in `design-accepted/`.

There is a remaining semantic failure: "make it premium and calm, remove pressure,
keep shipping and discounts unchanged" produced extra home sections and retained
the popup. It took two calls and 47.65 s (`design-premium-final/`). Further prompt
variants and a two-call option-selection prototype traded one failure for another;
they were not incorporated. The schema prevents malformed updates, not a model's
validly typed misunderstanding of the request. The draft still needs owner review.
This case remains in the reproducible probe and fails when those unwanted edits
occur; it is not counted as a successful check.

Run any case from the repository root with a loopback model already running:

```bash
PYTHONPATH=backend/src backend/.venv/bin/python verification/local-model-probe.py --case design-color-ko
PYTHONPATH=backend/src backend/.venv/bin/python verification/local-model-probe.py --case design-free-popup
PYTHONPATH=backend/src backend/.venv/bin/python verification/local-model-probe.py --case design-neon
PYTHONPATH=backend/src backend/.venv/bin/python verification/local-model-probe.py --case design-calm
```

Each invocation saves requests, responses, before/after options, usage and detected
unexpected changes. It returns a nonzero exit status for a failed expectation.

## Reproduced application defects

- Pending model replies allowed concurrent editing, saving and deletion. A late
  reply could overwrite newer draft edits. The full designer now stays disabled
  until the reply succeeds or fails. Failed requests retain the entered request.
- A manually entered delivery fee stayed visible after AI changed the canonical
  fee, so the displayed amount differed from the saved amount. Applying or undoing
  a changed option clears that option's stale money text, while preserving unrelated
  invalid product/ad inputs and their save blockers. USD, KRW and JPY cases each
  failed before this correction and passed afterward.
- Binary/banker's rounding disagreed with the form at half-minor-unit boundaries.
  For example, USD 1.005 became 100 rather than 101 cents; KRW 0.5 became zero.
  Decimal half-up conversion now matches the form. Four of seven boundary examples
  failed before this correction; all seven passed afterward.

## Focused verification

- 27 backend tests passed on the final merge in 6.10 s: design API, draft preview, decimal boundaries,
  real SDK/HTTP transport parsing in JSON and JSON Schema modes, retry and cache
  behavior for duplicates, unknown fields, null, wrong type and out-of-range values.
- 58 frontend tests passed on the final merge in 13.22 s across SiteDesigner,
  RunLauncher, OnlinePageIdentity and surveyPackagesOnline. Includes pending
  success/failure, display/undo, retention of unrelated invalid edits, conversation
  retention across saves and preview debouncing.
- Backend strict type check: zero errors and warnings. Frontend TypeScript passed.
- Backend boot passed and all thirteen changed frontend source/test files passed lint.
- The production frontend build passed in 18.94 s with existing chunk-size and Babel
  plugin timing warnings.
- The SDK transport tests emitted the pre-existing LiteLLM asynchronous logging
  cleanup warning; no live external provider was used by those tests.
- The upstream package survey test has a mock-reset warning for the models query;
  both package variant tests passed. No production model request was made by it.
