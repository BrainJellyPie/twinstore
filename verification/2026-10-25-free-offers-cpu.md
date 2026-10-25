# Free offers and copied product labels with a tiny CPU model

Date: 2026-10-25. Based on main `81a5d35beb3e6904bfdad952a6eb634eb50418c7`.

## Actual reproduction

Qwen3.5-0.8B Q4_K_M ran through the production layout editor with llama.cpp
b11878, five CPU threads and no GPU offload. Each probe used a fresh application
cache and applied the generated edits to a real domain store. The harness checks
price, reference price, sign, identity, placement and untouched products.

“Make only Mineral Water free” and “100 percent discount” produced `percent:
-100`. Both failed on both attempts because the application rejected discounts
beyond 90%, even though zero-priced products are supported.

During the broader Korean probes, the model returned `Green Tea 5,000원` or
`Green Tea 4,000원 (Drinks, level 1)` as the product name. The price and location
came from the actual prompt listing, but the application required the bare name
and rejected both attempts. This was an output-shape error with a known target.

## Changes

Discounts allow -100, giving a zero selling price while retaining each placement's
original reference. Physical and online stores share this behavior. Existing
ordinary discounts retain their previous regular-price semantics.

The target resolver accepts a product name, that name with its actual displayed
price, or the full displayed label with shelf and level. It only accepts labels
constructed from the current store. Invented prices/locations and collisions
with another product's actual name remain errors; it does not strip arbitrary
suffixes or choose a fuzzy match.

## Experiments deliberately not shipped

An extra 10% reduction of an already discounted $4 product with a $5 reference
was interpreted as an ordinary discount, producing $4.50. We tested explicit
basis flags, named basis values, separate discount operations, additional examples,
shorter prompts and a required summary before the changes. Some improved an
individual case but broke existing combined edits, whole-shelf changes or Korean
price instructions. Those broader changes were removed. Their raw outputs remain
under `/workspace/scratch/cpu-vlm-probe`; the discarded patch is
`/workspace/scratch/discount-basis-experiments.patch`.

The committed harness retains English and Korean extra-discount cases as semantic
checks; a completed response is not automatically a successful result. A bare
“make free” request permits either a zero everyday price or a 100% discount with
the original was-price. The explicit “show the original price” case requires the
reference to be retained.

## Reproduction

With the separately managed CPU server running:

```bash
PYTHONPATH=backend/src backend/.venv/bin/python verification/local-model-probe.py --case layout-free-item
PYTHONPATH=backend/src backend/.venv/bin/python verification/local-model-probe.py --case layout-full-discount
PYTHONPATH=backend/src backend/.venv/bin/python verification/local-model-probe.py --case layout-extra-discount-ko
```

The harness also covers ordinary discounts, sequential price/discount/sign edits,
moves, whole-shelf prices and Korean price changes. Artifacts include raw HTTP
bodies without headers or keys and before/after stores. Server prefix caching can
influence timings; these runs test correctness, not general performance.

## Final actual results

The final patch retains the previous prompt verbatim: broader prompt changes did
not reliably preserve behavior in this model. Eight of ten actual probes passed:
ordinary reference-price discount, ordered price/discount/sign edits, explicit
100% discount with reference retained, free offer, discount plus another product's
sign, eye-level move, whole-shelf price reduction and the Korean exact-price edit.
The 100% discount case needed two calls; the other passing cases used one.

Both English and Korean additional-discount probes remain failed: the model
selected a regular-price discount, leaving the underlying ambiguity unresolved.
The English $4 item became $4.50 rather than $3.60. These failures are deliberately
visible and are not counted as successful runs. The final raw runs are
`layout-*-1792957647643136944` through `layout-*-1792957693369358766` in the scratch
probe directory, with console logs named `final-unchanged-prompt-layout-*.log`.

## Focused verification

461 backend tests passed in 11.55 seconds, including USD/KRW, already-discounted
products, multiple placements with different references, physical/online parity,
source preservation, -100/-100.01 boundaries, canonical cache round trips and
invented or ambiguous copied labels. Strict backend type checking reported zero
errors and warnings; backend boot passed. No frontend change remains in this patch.
