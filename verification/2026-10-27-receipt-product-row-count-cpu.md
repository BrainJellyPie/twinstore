# Stop small-model receipt padding and retain the printed price columns

## Failure and implementation

Qwen3.5-0.8B on CPU transcribes the two actual rows of a mixed return receipt,
then repeatedly emits unnamed rows with zero quantity and prices. The original
6144-token run still has no response after over 120 seconds and at least 3965
generated tokens; it is cancelled rather than waiting through large retries.
A diagnostic 768-token, zero-retry call preserves the repeated objects in the
raw truncated reply. Simply asking the model to stop padding ends generation
but copies subtotal, tax, total, cash and change as additional products.

The receipt model now observes `product_row_count` before writing `lines`.
The prompt tells it to include each actual product row once, close the array
at that count, and exclude financial footers and empty padding. A declared
non-null count must equal the number of returned rows before validation/caching
succeeds. Boolean, negative and fractional counts are rejected. Missing/null
counts remain compatible with older partial/cached records. There is no new
row ceiling, no dropping of rows, and no reduction of the 6144-token budget.

Count-only testing reveals another problem in the 0.8B Korean fixture: it
reads the printed line amount 5000 as the unit price and calculates 10000.
That amount error also exists on unchanged main 459, but removing false footer
rows could allow the wrong amounts through review. The count-only candidate
is therefore **not published**. The final prompt maps English/Korean column
labels explicitly and requires independent transcription of printed values,
without calculating line totals. These instructions precede the final row-count
instruction; the reverse order still produced footer rows and was withheld.

Counts and field instructions aid transcription; they do not independently
authenticate an image or guarantee correct OCR. The guard checks consistency
between declared count and returned list, not the true number in the photo.

## Actual CPU evidence

Both models use Qwen3.5 Q4_K_M with their F16 vision projectors, llama.cpp
b11878, five CPU threads, zero GPU layers, context 8192, 512 image tokens,
reasoning disabled and temperature/seed zero. 0.8B runs on port 8081 and 2B
on 8082. Synthetic receipt images were visually inspected.

Twenty-two completed inference runs/HTTP replies, all with fresh application
caches, plus the one cancelled request. Exploratory bounded calls use 768
tokens and no retries only to inspect failure cheaply. **Every final case below
uses the production 6144-token budget and normal receipt retry setting**, with
one request/attempt and no application cache hits. Server prompt KV reuse is
possible, so timings are not a model-speed benchmark.

| Final model / case | Mode | Seconds | Result |
| --- | --- | ---: | --- |
| 0.8B / fractional return | Native schema | 8.42 | Exactly two rows, negative signs preserved, CSV blocked |
| 0.8B / Korean KRW subtotal only | Native schema | 7.92 | Correct 2500/5000 tea prices, no footer products, final total unknown |
| 0.8B / all products free | Native schema | 8.14 | Both actual products, zero amounts/total, CSV ready |
| 2B / fractional return | JSON | 22.14 | Exactly two signed rows, CSV blocked |
| 2B / unreadable prices | Native schema | 15.41 | Unknown prices remain null, known water amount retained, CSV blocked |
| 2B / all products free | JSON | 21.82 | Two free products retained, CSV ready |
| 2B / Korean KRW subtotal only | JSON | 15.00 | Correct product amounts, total unknown, no footer products |

All seven pass products, quantities, unit/line amounts, total, currency,
date/time, review readiness and applicable CSV checks. Their production
`vision_inputs.py` SHA-256 is
`f64c1e41ab0f295e16d1921eb26612744cb514f5a36fda4016e62327fce057a1`.

**Remaining observed limitation:** in the bounded 0.8B plain-JSON free-product
case, the model copies the JSON Schema instead of receipt data and hits the
diagnostic limit. The same failure occurs on unchanged main 459. This pass
does not claim to fix that output mode. The final 0.8B successes use native
schema output. The two scratch candidates that only append prompt text retain
the original file hash; their actual prompt changes are recorded in requests.
Compiled scratch-module candidates record their own file paths/hashes.

The complete run index is `/workspace/scratch/receipt-product-row-count-run-index.json`.
Evidence directories and all exact request/reply/image/result paths are in that
index. Final roots are `receipt-count-columns-final-small` and
`receipt-count-columns-final-2b` under `/workspace/scratch/`.
The cancelled run's directory under `receipt-small-model-cpu` has
`interrupted.json`; no completed reply is claimed for it.

## Deterministic and branch checks

Eleven new count-validation/cache checks fail against unchanged main 459
(2.81s). The count implementation passes 393 tests in 18 receipt/currency
engine/server suites (10.99s, 113 existing LiteLLM logging warnings), including
unknown/free/returned product rows, zero/legacy counts, 600-row compatibility,
retries before caching, money bounds, metadata, matching, review and uploads.
The later change only adjusts prompt text; the 35 final contract tests pass
in 3.09s, strict Pyright has zero errors/warnings, server import prints OK,
and the probe compiles. Actual-model cases also verify that final source.

Also merge `claude/online-shopping-features-ji7y0f` at
`bf2b48051e0567a83b556d883f52119b4653b162`. Its two commits expose full truncated
labels on hover and connect invalid form fields to their explanations,
including localized hourly staffing errors. Nine affected frontend suites
pass 310 tests in 16.34s. TypeScript and changed-file ESLint are clean; Vite
builds in 20.72s with the existing chunk-size warning. This is DOM/build
verification, not a browser smoke. Both sides of the Unreleased conflict are
retained; v0.8.2 and older changelog bytes, tags and assets remain unchanged.
Logs use `/workspace/scratch/receipt-count-` and `ui-field-guidance-`.
