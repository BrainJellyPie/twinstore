# Exact SKU identity in scenario targets

Scenario matching lowercased every SKU before applying a promotion or stockout.
For distinct products `tea`, `TEA` and `Tea`, selecting one exact ID therefore
changed all three. Combined stockouts and discounts could also remove products
that should have remained on sale. Fifteen new cases failed before the fix;
four single-SKU case-insensitive controls already passed.

Exact trimmed targets now match the original SKU first. Case-insensitive SKU
fallback remains available only when the folded key resolves to one distinct
SKU. Ambiguous fallback targets affect nothing and the existing draft-preview
warning reports that they were omitted. Product/rack labels and keyword rules
retain their previous precedence after SKU resolution.

Validation covered 21 new cases: ASCII/hyphenated/Greek SKU families, whitespace,
discounts and stockouts, ambiguous and unique fallback, simultaneous effects,
unchanged source layouts and blank targets with an empty legacy SKU. The
existing preview uses the same matcher. The combined scenario/preview run
passed 78 tests in 6.35 seconds; the final blank-target guard was checked with
38 matching tests in 0.28 seconds (80 distinct tests across these runs).
Strict Pyright passed for both changed production modules. No model calls ran.
