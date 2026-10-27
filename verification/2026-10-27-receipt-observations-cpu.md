# Complete receipt rows and explicit printed-field instructions

## Observed failures

On main `c98db74f`, the actual local Qwen3.5-2B Q4_K_M VLM returns a store,
currency and total for a legible two-product receipt but omits every product
line in native-schema mode. Date and time are empty despite being printed.
USD and KRW examples reproduce this (10.30 and 8.93 seconds, one HTTP call
each). The receipt schema makes the entire item list optional; validation
accepts the empty reading. Later review correctly blocks exporting no items.

Plain JSON reads both products and their amounts, but replaces the printed
6.60 total with the 6.00 subtotal (20.04 seconds, one call). These are actual
recognition/response failures; no model replies are mocked.

## Change and intermediate checks

The model-facing receipt schema requires explicit values for every receipt
and product-row field. Wire defaults are removed so the format describes
observations. Runtime defaults remain for existing partial transcriptions;
unknown strings, null amounts and a genuinely empty item list are still
representable. Product names, count/weight, unit price and row amount have
column descriptions. Existing bounds and boolean/nonfinite guards remain.

Requiring fields alone restores quantities and amounts, but names and dates
remain empty. Removing wire defaults and adding field descriptions alone
also fails that native example. The final prompt therefore names the JSON
fields and explicitly maps printed product text, QTY, UNIT and AMOUNT into
the corresponding fields. It distinguishes the printed final total from
subtotal/payment/change and specifies missing-time and printed-zero handling.
No expected product names, quantities or amounts from the fixture are supplied
to the model outside the image.

The first column-prompt candidate reads normal USD receipts correctly in both
output modes and passes KRW, fractional, free-product and foreign-currency
controls. Boundary checks find invented `17:00` on a date-only receipt, a
missing visible zero total on a cancelled transaction, and a subtotal copied
into an absent total. Explicit missing-time and zero-total instructions correct
the first two. The subtotal-only failure remains and is not presented as fixed.

## Final CPU results

llama.cpp b11878, CPU only, 5 threads, context 8192, reasoning disabled, image
budget 512 tokens, seed/temperature 0, production receipt output cap 6144.
Each case uses a fresh application cache and one real HTTP call; warm server
prompt reuse is possible. Synthetic 512×520 receipt fixtures were visually
inspected, including the date-only, cancelled and subtotal-only variants.
The probe saves the original image, actual JPEG input, requests and responses,
reading, product matching, review, CSV and explicit expected-field checks.
It does not read or write a user project.

| Case / output mode | Observed result | Seconds |
| --- | --- | ---: |
| USD with tax / native | Both products, quantities, unit/row amounts, timestamp and 6.60 total correct | 13.50 |
| USD with tax / JSON | Same correct fields; no payment or tax product rows | 19.84 |
| KRW / native | 2500×2 and 1000×1 retained as won; total 6000 | 14.82 |
| Fractional quantity / native | 0.5×4.00 gives 2.00; CSV preserves fractional quantity and amount | 13.83 |
| Free product / JSON | Free product retained with zero unit/row amounts | 20.05 |
| EUR receipt in USD store / native | Printed EUR retained; review blocks currency mismatch | 14.84 |
| Date only / native | Date retained without a fabricated time; review flags missing time | 15.13 |
| Cancelled, zero total / native | No invented product rows; printed total 0 retained; empty receipt stays blocked | 11.94 |
| Subtotal only / JSON | **Fails:** absent final total is filled with subtotal 6.00 | 19.51 |

Eight of nine final-code cases pass. The unchanged primary worktree at
`c98db74f` also reproduces the subtotal-only failure in JSON mode (18.59 seconds,
source SHA-256 `829297be28a23988eaec559cb29f18a08cad67844bd710bf3de443d0e21d454b`).
In that case purchased-line amounts and their CSV remain correct, but receipt
metadata is inaccurate. Review cannot detect an invented amount that happens
to equal the included product subtotal. This remains an open model-evidence
problem; these checks do not establish accuracy on arbitrary receipt photos.

Across baseline, intermediate candidates, controls and final code: 25 completed
runs, 25 HTTP calls, zero application cache hits. Raw artifact roots are listed
in `/workspace/scratch/receipt-explicit-observations-run-index.json`. Final
positive runs use `receipt-explicit-observations-final`; missing-evidence cases
use `receipt-missing-evidence-candidate`; the unchanged-main comparison uses
`receipt-main-boundary-control`. New probe `verification/local-receipt-probe.py`
exits nonzero for a failed semantic check and records the production source
path/hash, preventing structural parsing from being counted as full success.

## Deterministic verification

The wire-contract regression tests initially fail 9 checks and pass 6; all
15 pass after the change. The full selected receipt/photo-input scope passes
318 tests across 15 engine/server files in 11.13 seconds. It covers optional
metadata, unreadable names, currencies, fractional/zero amounts, overflow,
invalid numeric values, output budgets, cached reads, matching, review/export,
timestamps and batch isolation/streaming. There are 110 existing LiteLLM async
logging warnings. Strict Pyright and server import pass; probe compilation
and diff checks pass. Frontend validation is inherited from integration 453.

A final strict-typing correction specifies `list[_ReceiptLineVLM]` as the
empty-list factory. The 15 wire/runtime tests are rerun (0.41 seconds), and
serialized schemas and prompts are compared byte-for-byte before/after this
annotation correction; the requests supplied to the model are unchanged.
The inference-source SHA-256 is
`c71d0eb43f334a5a262480faaaf74ef1e79100e9c74b59927d80bfb01c595ee5`.
Comparison evidence: `/workspace/scratch/receipt-wire-before-typefix.json`.
The v0.8.2 changelog and release assets are unchanged.
