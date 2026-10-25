# Preserve visits when model action vocabulary changes case

The action schema rejected known values such as BUY, PATH and lowercase shelf
faces, including otherwise valid values surrounded by whitespace. A single
variant could exhaust model attempts and discard a planned or impulse purchase
sequence. These values have unambiguous canonical equivalents in the existing
action vocabulary.

IntentResponse now canonicalizes only action, nav and face on a copied model
action dictionary, before classifying fields as unused by non-purchase actions.
This order matters: BUY with quantity or SKU set to null must remain invalid,
not acquire the defaults allowed for browsing or payment. Unknown vocabulary
and wrong types remain invalid. Product SKUs, offer codes, quantities and
positions are not case-normalized. Authored CustomerAction validation is
unchanged, and engine-only action hints continue to be removed.

Thirty-two actual LiteLLM/Instructor HTTP cases cover both JSON modes, both
route orderings, planned and impulse stages, and separate or combined spelling
changes. Each executes three units of sku-a plus one sku-b for total spend 500,
one payment and an exit; it checks the original layout, canonical cache output
and validation of deliberately altered cached spellings. Twenty-eight strict
JSON controls cover every action/face pair and retain area coordinates, exact
SKU spelling and source-input immutability. Twelve controls verify null purchase
fields remain invalid after BUY normalization, twelve reject unknown values,
and one preserves authored-domain validation.

The unchanged implementation failed 72 cases and passed 13 in 6.24 seconds.
The focused action-boundary, internal-field, compact-catalog, quantity and
optional-impulse suite passed 344 tests in 9.57 seconds. Full source Pyright
reported zero errors and warnings. Eight known LiteLLM asynchronous logging
cleanup warnings were emitted. HTTP responses are scripted; no native model
inference, downloads or paid calls ran.
