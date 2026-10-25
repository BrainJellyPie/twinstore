# Keep uncertain receipt identities out of automatic sales matching

A receipt naming Coca-Cola Original 1500ml was automatically assigned to a
store's 500ml SKU by character similarity. The review endpoint considered the
known SKU valid and allowed CSV export, assigning the larger product's sales
to the smaller one. Flavors, brands, pack counts, percentages and Korean size
labels reproduced the same issue.

Automatic receipt matching now requires a unique full normalized name.
Case, punctuation, spacing and Unicode-width normalization remain; ambiguous,
similar and abbreviated labels retain their names, quantities and amounts for
manual product selection. Review blocks export until an unmatched line has a
valid selected SKU or is excluded. The former abbreviated-label test was
updated to require review rather than assume an identity from similarity.

Before the change, 38 checks failed and 20 controls passed. The focused
receipt and photo-input suites now pass 157 checks in 6.73 seconds; full-source
Pyright reports zero errors and warnings. Twenty-four tests use real
LiteLLM/Instructor with scripted HTTP in JSON/JSON Schema modes and USD/KRW.
They verify wrong-SKU exclusion, preserved paid amounts for fractional
quantities, manual correction, POS CSV round-trips and cached OCR reuse.
API cases cover both catalog orders and verify unmatched receipts fail review.

No native OCR/model inference, weights or paid calls were used. This verifies
identity handling for supplied transcriptions, not recognition accuracy.
Existing third-party LiteLLM logging cleanup warnings remain.
