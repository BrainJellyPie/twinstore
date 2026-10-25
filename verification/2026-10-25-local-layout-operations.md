# Layout edits: CPU model fields, operation meaning and scope

Date: 2026-10-25. Includes integration of online bridges and command-bar questions
through `d8b2f6278df5f8570c8471fbc04247137b764624`.

## Actual failures

Qwen3.5-0.8B Q4_K_M ran on five CPU threads with llama.cpp b11878, no GPU offload,
an 8,192-token context, temperature 0, seed 0 and the production layout editor's
1,500-token output budget. Requests used the production LiteLLM/Instructor path
and JSON Schema output. Each case used a fresh response cache.

The fixture has a Drinks shelf with Green Tea and Mineral Water, a free eye-level
slot and a separate Snacks shelf with Potato Chips. Actual output exposed three
different problems:

1. “Move Green Tea to eye level on its current Drinks shelf” put `Drinks` in
   `category`, omitted `shelf` and repeated that mistake on retry. Both calls failed
   to produce an applicable move (6.61 s total).
2. “Discount Green Tea by 10 percent and put a SALE sign on Potato Chips” returned
   an everyday-price operation instead of a discount. The amount became $4.50,
   but the $5.00 reference price was lost, changing what shoppers see on the tag.
3. “Reduce all prices on the Drinks shelf by 10 percent” also emitted an unchanged
   price operation for Potato Chips on the other shelf. Applying that operation
   erased its existing $3.00 reference price, although its $2.00 price was unchanged.

The third problem is why checking only the resulting prices is insufficient.
The saved before/after product fields and placements were compared directly.

## Change

The wire schema now selects an object shape by operation kind. A move requires
`product` and `shelf`, with an optional valid `level`; a discount requires a negative
`percent`; price, promo and category-price changes require their corresponding
targets and values. Unused fields are excluded from that operation's wire shape.
Canonical cached objects remain readable, and existing runtime application checks
still reject unavailable or ambiguous targets and request a bounded correction.

The prompt explains that percentage instructions use percentage operations,
whole-shelf edits use `category_price`, and combined requests need all their edits.
Two compact examples distinguish discount-plus-sign from a shelf price change.
Schema-only experiments improved the move but still omitted a sign or touched
the wrong shelf; those experiments were not treated as successful verification.

## Final actual observations

| Request | Result | Calls | Time |
| --- | --- | --- | --- |
| Tea at eye level | Drinks shelf, level 3; other product fields unchanged | 1 | 1.30 s |
| Tea 10% off plus SALE on chips | Tea $4.50, reference $5.00; chips sign set | 1 | 3.33 s |
| Drinks shelf 10% lower | Tea $4.50, water $0.90; chips $2.00 and reference $3.00 preserved | 1 | 1.42 s |
| Korean request: tea only, KRW 3,000 | Only tea price changed from KRW 5,000 to 3,000 | 1 | 3.10 s |

These timings are observations from sequential local runs, not a general benchmark;
llama.cpp can reuse a prompt prefix even when the application response cache is fresh.
Four passing cases do not prove arbitrary instructions are interpreted correctly.

The checked-in harness includes `layout-move`, `layout-discount-promo`,
`layout-category` and `layout-price-krw`. It compares every product field and
placement against the intended changes and preserves a discounted unrelated
product as a scope check. Run it against a separately started local CPU server:

```bash
PYTHONPATH=backend/src backend/.venv/bin/python verification/local-model-probe.py --case layout-category
PYTHONPATH=backend/src backend/.venv/bin/python verification/local-model-probe.py --case layout-discount-promo
```

Both commands were also executed from the checked-in harness with fresh caches:
one call each, 1.22 s and 1.52 s, with field/placement comparisons passing.
The harness saves raw HTTP bodies without headers/keys and before/after layouts.
Investigation artifacts are under `/workspace/scratch/cpu-vlm-probe/layout-*`.

## Focused verification

589 backend tests and 31 frontend tests passed. They cover operation grammars,
malformed-field correction and cache behavior, reference prices, null/unused
fields, long/ambiguous names, accessible moves, layout saves, command routing,
online/physical price transfer and shelf-test transfer. Existing LiteLLM cleanup
warnings and a missing-model-list mock warning were emitted.
Strict backend type checking passed with zero errors/warnings; backend boot,
frontend TypeScript, changed-file lint and the production build (19.48 s) passed.
