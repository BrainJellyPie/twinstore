# Ambiguous captured product matching

Existing-product matching kept only the first placement for each normalized name.
Two different SKUs called Tea could therefore redirect the same captured product
to either SKU merely by reversing rack order. Estimated prices could similarly
inherit an arbitrary offer, and equally close fuzzy names had no ambiguity check.

Matching now considers all offers for the selected names. An already-known
captured SKU is preserved; otherwise reuse requires one distinct candidate SKU.
Equal-best fuzzy matches are considered together. Ambiguous identities retain
their captured SKU with a review note. Estimated or absent prices are replaced
only when matching offers for the chosen SKU have one distinct price; actual
read prices remain authoritative.

Verification:

- Initial engine reproduction: 24 failed and 7 passed in 0.65 seconds.
- Final engine and related capture API checks: 80 passed in 6.02 seconds.
- Two additional API checks passed in 3.23 seconds, exercising both catalog
  orders through preview and save. Existing identities and captured identities
  stay distinct, and saved crop images remain attached to the captured SKUs.
- Covers exact/fuzzy matching, Unicode and punctuation normalization, six
  permutations of tied names, explicitly known identities, duplicate placements,
  multiple prices and missing/estimated/read prices. Source objects stay intact.
- Pyright on the changed planogram module passed. All checks were offline.

An ambiguous name is not enough evidence to merge products. These cases require
review; no price-based identity inference or historical data migration is added.
