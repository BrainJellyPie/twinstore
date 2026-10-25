# Preserve the requested basis of automatic price edits

The layout editor reused A/B-draft conversion, which marks explicit price
changes `keep_reference=True`. A model correctly returning an everyday price
of 1.49 for a product costing 1.99 therefore saved an unintended reference
price of 1.99. A subsequent 10% discount in the same draft used that old basis
and saved 1.79, rather than 1.34. Existing promotional reference prices made
the discrepancy larger. The reference also affects simulated price response
and was-price labels.

Layout-draft conversion now resets that flag for explicit everyday-price
operations before applying subsequent changes. Preview application uses the
same layout semantics as saving, so category-price previews no longer claim
that shoppers remember prices which saving clears. The prompt distinguishes
an everyday-price replacement from a discount. A/B drafts, explicit manual
`keep_reference=True` requests and discount-only edits retain their semantics.
Original layouts and already saved edits are not rewritten.

Forty-eight LiteLLM/Instructor HTTP cases cover both structured modes, USD and
KRW, existing or absent reference prices, lower/higher/unchanged prices,
price-before-discount, discount-before-price, and category changes. They check
both facings, exact final price/reference pairs, untouched unrelated products
and signs, preview/save agreement, repeat-cache reuse and source immutability.
Four controls preserve explicit references and model-written A/B comparisons.
The pre-fix run failed all 48 affected cases while the four controls passed
in 3.83 seconds. An existing API draft/save test now verifies the persisted
reference price and agreement with the preview.

The focused layout, experiment, marketing, generated-price and layout API suite
passed 350 tests in 16.61 seconds. Its 113 warnings were the existing LiteLLM
logging-worker cleanup warning. Full source Pyright reported zero errors and
warnings. Responses were scripted through the actual HTTP client; no native
model inference, weights or paid calls were used. This establishes conversion
correctness for those responses, not how often a real model selects them.
