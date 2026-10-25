# Do not equate rival products from name similarity alone

The deterministic comparison treated Coca-Cola Original 500ml and 1500ml as
the same product. Vanilla/Banana, different brands, pack counts, percentages
and Korean size labels reproduced the same issue. Similarity also removed
these names from the model-matching request. A 200/400 price example reported
a 2.0 price index and 0.67 pull factor despite comparing different products.

Only normalized exact names and explicit aliases now establish a match.
Other names reach the existing optional model matcher, whose prompt requires
the same brand, variant and size. Without a confirmed alias they remain
unmatched, including when matching is disabled or its provider fails. Case,
spacing, punctuation and Unicode-width normalization remain supported.
Misspellings now require an explicit alias; character similarity alone is
insufficient evidence for a price or assortment comparison.

Before the fix, 28 new checks failed and four exact-name controls passed.
The focused comparison/API suites now pass 131 checks in 5.16 seconds.
Full-source Pyright reports zero errors and warnings. Twenty-four checks use
real LiteLLM/Instructor with scripted HTTP responses in JSON and JSON Schema
modes, reversed item order, six identity differences, mixed matched/unmatched
assortments and cache reuse. API checks request apply=true and verify saved
town bytes and pull history remain unchanged for unmatched variants, with
matching disabled, returning no match, or failing.

These checks validate routing and calculation boundaries, not a native
model's ability to identify products. No weights or paid calls were used.
The existing third-party LiteLLM logging cleanup warnings remain.
