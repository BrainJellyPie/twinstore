# Undefined sales-rank correlation

## Failure and change

Three products each selling one unit in both simulated and real receipts
previously produced SKU share similarity 1 but SKU rank correlation 0. A store
with one rack/category group also always received rack rank correlation 0.
The interface labels a numerical zero correlation as poor, even though
correlation is undefined when either rank vector has no variation.

Return an undefined internal correlation for empty/singleton or constant rank
vectors. Fidelity reports serialize this as the existing nullable metric value
and explain the required variation in report notes. The current frontend
already renders null as unavailable without a quality verdict. Shared-SKU rack
ambiguity remains a separate exclusion reason.

This leaves valid measured zero correlations, positive/negative correlations,
ties with remaining variation, share similarities, NDCG conventions, basket
distances and receipt counts unchanged. It does not rewrite historical reports.

## Verification

- Baseline: 50 regression failures, 4 valid numeric controls; 0.52 seconds.
- Constant vectors on either/both sides, lengths 0/1/2/3/1000 and zero/positive/
  negative constants are unavailable. Perfect/inverse/zero correlations and
  nonconstant tied ranks remain numeric.
- Matching uniform SKU sales, one product and one category preserve separately
  defined metrics while withholding rank scores. Strict JSON serialization
  succeeds without NaN/Infinity.
- Corrected an older single-category assertion that had accepted the artificial
  zero rank score. Its two-category control continues to score 1.
- 446 focused analysis/fidelity/returns/shared-rack checks passed in 1.23 seconds.
  Changed-module Pyright reported zero errors/warnings.
- No frontend changes, full suite, paid model calls or historical-data mutation.
