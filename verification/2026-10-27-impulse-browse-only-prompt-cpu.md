# Keep a full basket's impulse prompt consistently browse-only

After the capacity-schema fix, a real JSON-mode full visit still emitted an
extra buy with no product code. Its original Green Tea purchase succeeded,
but the malformed additional action was discarded. The prompt prohibited
additional purchases while still explaining how to write buy events,
quantities and browse→buy pairs.

When the validated planned basket fills the pattern's product allowance,
the prompt now asks for browse reactions only and omits those purchase
instructions. The explicit no-additional-purchase instruction comes last.
When capacity remains, the purchase, quantity and prior-browse instructions
remain available. Product/exposure data and the planned basket are retained.
This does not change response schemas, canonical validation, routing or
retry counts. A generic missing-SKU validator was not introduced: the
default engine call has one attempt, and rejection alone would fail a visit
whose original basket is valid.

## Real CPU evidence

All runs use Qwen3.5-2B Q4_K_M on llama.cpp b11878 with five CPU threads,
no GPU, context 8192, reasoning disabled, temperature zero and fresh caches.
Each run executes all three model stages and receipt execution, making
three real HTTP calls with zero application cache hits.

| Case | Seconds | Purchase and receipt checks |
| --- | ---: | --- |
| Before: paid tea / JSON | 60.75 | Correct original purchase; malformed additional buy dropped |
| After: paid tea / JSON | 55.81 | Exactly one tea for 250 minor units; no additional buy or invalid drop |
| After: free tea / native | 36.85 | Exactly one free tea; one payment and exit; no additional buy or invalid drop |
| After: browse only / JSON | 58.94 | No purchase, no payment, exit; browse reaction retained |

For the paid JSON comparison, both initial requests and replies are
identical, as is the impulse user message. Only the impulse system prompt
changes. The final response is a browse reaction, so no purchase repair or
post-processing substitution creates the passing result. Timing is a single
observation, not evidence of a general speed improvement.

Narration and location accuracy remain separate open issues. The paid JSON
reply invents a 10% coupon; the free native reply still targets `[-1, 2]`.
Existing route sanitation bounds executed coordinates, but this does not
make the model's intended browse location correct. The browse-only JSON
reply stays on a walkable tile; matching the correct product-facing side is
not established by that check. Generic incomplete buy responses can still
reach the executor when a non-enforcing provider ignores the prompt.

The probe now names its purchase-only model check `model_purchase_plan_ok`
instead of the overly broad `model_semantic_ok`. It also separates correct
receipt contents from invalid-action drops and reports whether model targets
are walkable. Overall `success` still refers to purchase/receipt checks;
the location flag is a separate diagnostic and narration is not scored.
The paid run precedes this diagnostic rename; its original artifacts are
preserved.

## Verification

Eight related test files pass 268 tests in 16.70 seconds, without warnings.
Strict Pyright reports zero errors and warnings; server import, probe
compilation and diff checks pass. Frontend validation is inherited from
integration 445.
Raw requests, replies and receipts are in
`/workspace/scratch/impulse-browse-only-final`, with run suffixes
`one-json-1793075729571283030`, `free-json_schema-1793075851034487984`
and `browse-json-1793075890212544811`. Input/reply equality is recorded
in `impulse-browse-only-reproduction.json`; logs and the selected test list
use the same prefix. Reproduce with
`verification/local-intent-probe.py --case one --mode json --full`.
This is Unreleased; v0.8.2 assets and published notes are unchanged.
