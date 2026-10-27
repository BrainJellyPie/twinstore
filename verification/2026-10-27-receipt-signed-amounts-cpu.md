# Preserve receipt return signs before sales review

## Actual failure and change

On main 458, the CPU model reads a mixed return/purchase receipt's
`GREEN TEA -1 2.50 -2.50` as quantity **+1**, unit price 2.50 and line amount
**+2.50**. Four bottles of water remain 4.00 and the printed final total remains
1.50. All names match the catalog, so review allows a sales CSV with a subtotal
warning. The returned item has incorrectly become a positive purchase.
This is a real native-schema inference failure, not a mocked invalid reply.

The receipt prompt now explicitly includes returned/refunded product rows and
preserves printed negative quantities and amounts. It forbids converting them
to their positive absolute values. The existing review already rejects negative
quantities and refund amounts; it can now see that evidence in these cases and
withholds CSV. Review rules, schemas, numeric conversion and discount handling
are unchanged. This prompt improvement is not a deterministic guarantee against
every future OCR sign error; a model that still reports entirely positive
numbers can still require manual correction.

The reusable probe adds integer and fractional mixed-return fixtures and checks
that a receipt requiring correction cannot produce a sales CSV. Fixtures are
visually inspected, use clear synthetic print, and do not establish accuracy on
arbitrary camera photos. Expected products/amounts come from the fixture, not
the model reply.

## CPU evidence

Qwen3.5-2B Q4_K_M and F16 vision projector, llama.cpp b11878, five CPU threads,
zero GPU layers, context 8192, 512 image tokens, reasoning disabled,
temperature/seed zero. Nine actual runs and nine HTTP requests/attempts,
zero application cache hits; server prompt KV reuse is possible.

The original failing run takes 15.69s. A process-local prompt-only experiment
takes 15.80s and succeeds. That exploratory driver's recorded file hash still
identifies the original source; its added prompt is visible in the saved request.
All seven final production runs record the new source hash below.

| Final case | Mode | Seconds | Result |
| --- | --- | ---: | --- |
| Integer return, English | Native schema | 7.21 | -1 and -250 cents preserved; no CSV |
| Fractional return, English | Native schema | 13.86 | -0.5 and -200 cents preserved; no CSV |
| Integer return, English | JSON | 20.51 | Signs preserved; no CSV |
| Fractional return, Korean labels | JSON | 13.98 | Signs and Korean product matches preserved; no CSV |
| Normal taxed purchase | Native schema | 15.89 | Products and 6.60 total preserved; CSV ready |
| All products free | JSON | 20.52 | Two free product rows and total zero preserved; CSV ready |
| Korean KRW subtotal only | Native schema | 15.35 | Total remains unknown; purchased amounts preserved |

All seven pass exact products, quantities, unit/line amounts, total, currency,
date/time, readiness and applicable CSV checks. Fractional return values differ
from the numeric examples in the new prompt. Final production SHA-256:
`385fc7e06344c3cae64bb1eb2449acf6a26dfca57509edace841da437a1698c3`.

Run index: `/workspace/scratch/receipt-signed-run-index.json`. Evidence roots:
`receipt-refund-cpu`, `receipt-refund-candidate`, `receipt-signed-final` and
`receipt-signed-controls` under `/workspace/scratch/`. Each preserves the
fixture, request image, raw request/reply and reviewed result. The initial
scratch drivers are `receipt-refund-probe.py` and `receipt-refund-candidate.py`.

## Focused checks

Seventeen engine/server receipt and currency suites pass **374 tests in 10.88s**,
with 113 existing LiteLLM async logging warnings. Coverage includes negative,
zero and missing amounts, native wire requirements, matching, review/CSV,
subtotal evidence, metadata, money bounds, currency and photo upload handling.
Strict Pyright reports zero errors/warnings, server import prints OK, the probe
compiles, and diff checks pass. UI validation is inherited from integration 458;
no frontend source changes here. Published v0.8.2 and all older changelog bytes
remain unchanged. Check logs use `/workspace/scratch/receipt-signed-`.
