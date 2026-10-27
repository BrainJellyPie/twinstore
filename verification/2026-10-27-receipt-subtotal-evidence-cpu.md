# Do not treat a transcribed subtotal as the final receipt total

## Evidence and change

Integration 454 leaves one observed failure: a mini VLM fills the absent final
receipt total with a visible subtotal, even when the prompt explicitly forbids
that substitution. Asking it to also copy the printed row reveals a usable
contradiction: `total_row="SUBTOTAL 6.00"` alongside `total=6.0`. The scratch
experiment returns exactly that in one real JSON-mode HTTP call (20.98 seconds).
Its uncorrected result remains failed; the reply is not edited.

The receipt response now requests that literal row before the numeric total.
A row beginning with a recognized subtotal label cannot establish a final total.
The reader leaves total unknown and retains the original row in the existing
review notes. It preserves product identities, quantities, unit/line amounts,
store, date/time and currency. Normal final totals, including zero, remain.
Existing partial/cached response data can omit the new observation; it does not
cause arbitrary other labels to be reclassified. Null row text becomes empty.

Recognition includes normalized English/Spanish SUBTOTAL, French SOUS-TOTAL,
Korean 소계/소계금액 and Japanese/Chinese 小計/小计, with Unicode-width and
spacing variants. The check is anchored to the row's beginning: a real TOTAL
row can mention a subtotal later without being discarded. This guard depends
on what the model transcribes. It does not independently authenticate the
image, recognize all possible languages/abbreviations, or detect a fabricated
TOTAL label. The full original label is retained for the user to review.

## Actual CPU verification

Qwen3.5-2B Q4_K_M, llama.cpp b11878, 5 CPU threads, no GPU, context 8192,
reasoning off, image limit 512 tokens, temperature/seed 0. Synthetic receipt
images are visually inspected; they are not a broad photographed-receipt
accuracy benchmark. Every run uses one real HTTP request and a fresh
application cache; server prompt KV reuse is possible.

| Final-code case / mode | Result | Seconds |
| --- | --- | ---: |
| Subtotal only / JSON | total unknown, source note `SUBTOTAL 6.00`, product CSV preserved | 21.60 |
| Subtotal only / native | Same correct handling | 16.58 |
| Normal taxed receipt / JSON | Products and 6.60 final total retained | 20.45 |
| Normal taxed receipt / native | Same correct reading | 15.87 |
| Date only / native | No invented time; review still requires missing time to be resolved | 13.90 |
| Cancelled transaction / native | No product rows; printed total zero retained | 10.20 |
| All products free / JSON | Both purchased rows, zero unit/line prices and total zero retained | 20.33 |
| Unreadable amounts / native | Quantities and readable prices retained; unknown amounts stay null, review blocks export | 14.74 |

All eight final cases pass. Both subtotal-only raw model replies still contain
`total=6.0` and the truthful `SUBTOTAL 6.00` row: the reader's guard, rather than
a claimed improvement in model judgment, prevents the false total. This repairs
the remaining recorded subtotal-only case from integration 454. Existing receipt
review/export preserves actual product-line amounts and tax/payment exclusions.

Nine completed runs including the initial uncorrected experiment, nine HTTP
calls, no application cache hits. Final results have the same production source
hash. The run index is `/workspace/scratch/receipt-subtotal-evidence-run-index.json`.
Evidence roots: `receipt-total-evidence-candidate`,
`receipt-subtotal-evidence-final`, `receipt-subtotal-evidence-boundaries` under
`/workspace/scratch/`. Scratch driver `probe_receipt_total_evidence.py` modifies
only a process-local candidate module; its initial reply is actual inference.
The reusable probe adds all-free and unreadable-price cases and avoids checking
CSV against unknown expected amounts when review should have blocked export.

## Deterministic checks

Thirty-three currency/label checks fail against the unchanged primary worktree
at main 455. The final focused scope passes 368 tests in 16 engine/server files
(11.36 seconds), including complete wire fields, multilingual subtotal evidence,
normal/zero totals, absent legacy evidence, quantities and prices, both HTTP
output modes, cached reuse, amount bounds, matching, review/export and photo
batch behavior. There are 114 existing LiteLLM async logging warnings. Strict
Pyright reports zero errors/warnings; server import, probe compilation and diff
checks pass. UI validation is inherited from integration 455. Published v0.8.2
notes and all older changelog text are byte-identical; release assets/tags do
not change. Logs use `/workspace/scratch/receipt-subtotal-evidence-`.
