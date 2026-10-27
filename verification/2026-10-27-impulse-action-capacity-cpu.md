# Reflect remaining purchase capacity in impulse response schemas

Real full-pipeline CPU visits previously proposed a second Green Tea even
though one planned purchase filled the pattern's one-product allowance.
The final receipt was correct only because existing budget or product-count
enforcement dropped the additional purchase. The prompt stated the limit,
but the native schema still offered buy, pay, exit and other visit actions.

Impulse wire schemas now offer only browse and buy, and omit buy when the
validated planned basket fills the product allowance. The same constraint
applies after context recovery. A short explicit prompt instruction also
states that no additional purchase is permitted. Browsing remains available;
the stage is not skipped. Available capacity still permits legitimate
impulse purchases, including free products. Canonical action validation,
cache readability, purchase quantities and final enforcement are unchanged.

## Real CPU runs and limits

Qwen3.5-2B Q4_K_M on llama.cpp b11878, five CPU threads, no GPU, context 8192,
reasoning disabled, temperature zero. Each full visit makes three real HTTP
calls and reports zero application cache hits. Pattern selection, intent,
impulse, routing, payment and receipt execution are exercised together.

| Case | Before | After |
| --- | --- | --- |
| Native, paid tea | 34.37 s; one extra buy removed by budget guard | 43.24 s; one planned buy, no impulse buy or dropped purchase |
| Native, free tea | 41.81 s; one extra buy removed by product-count guard | 44.13 s; one planned buy, no impulse buy or dropped purchase |
| JSON, paid tea | Not run for this comparison | 60.75 s; original tea purchased correctly, malformed extra buy dropped |

Both native cases retain exactly one Green Tea, one payment, exit and the
correct receipt total. They also retain browse reactions. The first two
request bodies are identical before/after in both cases; the free case's
first two replies are identical too. The paid intent reply differs despite
the identical request. Timing is observational, not a performance claim.

The JSON case is a **failure under the stricter probe checks**. Its planned
purchase includes `@P1` and succeeds, but its impulse response emits a buy
without `product_sku`. Canonical parsing defaults the missing SKU to an empty
string; the engine drops that invalid additional action. The receipt still
contains one Green Tea for 250 minor units. Thus this is not a lost original
purchase; it exposes a response-validation gap, which is the next target.
Native constraints do not prove correctness of non-enforcing JSON output.

The probe's `model_semantic_ok` flag checks purchase identities and quantities
only. It does not validate all semantics. The native replies still contain
out-of-grid browse coordinates and invented promotional narration. These
remain open; the existing route sanitizer keeps executed positions in bounds.

## Regression checks

The new focused test reproduces 36 failures before the change. Final checks
across 22 related files pass **995 tests in 31.82 seconds**, with 14 existing
LiteLLM coroutine warnings. Strict Pyright reports zero errors and warnings;
server import and diff checks pass. Coverage includes zero, full and available
capacity, paid/free offers, quantities larger than one, context recovery,
cache reuse, exposure, checkout and legacy/non-enforcing-provider guards.
Frontend checks are inherited from integration 445.

Actual artifacts are under `/workspace/scratch/impulse-action-capacity-final`:
`one-json_schema-1793075219337340736`,
`free-json_schema-1793075264953686397`, and `one-json-1793075311573083687`.
Previous full visits are in `intent-operation-fields-full`.
`impulse-action-capacity-reproduction.json` records input/reply comparisons.
Test logs use the same prefix. Reproduce using
`verification/local-intent-probe.py --case one --mode json_schema --full`.
This is an Unreleased correction; v0.8.2 assets and notes are unchanged.
