# POS aggregate overflow and fidelity JSON consistency

## Reproduction

Finite quantities/prices such as `1e200 × 1e200`, two `1e308` receipt values,
or totals spread across multiple products/receipts exceeded floating-point
range during fidelity calculation. Very small positive denominators such as
`1e-310` also produced infinite mean ratios.

The old API returned HTTP 200, with its response serializer converting infinite
metrics to null, while `fidelity.json` retained nonstandard `Infinity` values.
Thus an invalid upload replaced the previous evidence and the saved report did
not match the HTTP response. The baseline regression suite had 18 failures and
5 passing valid controls in 3.57 seconds.

## Change

Check absolute quantity and line-value totals for matched POS products before
computing metrics. Gross totals, rather than cancellation-prone net sums,
prevent row order from deciding whether extreme sales/returns are accepted.
An overflowing line product or aggregate receives HTTP 400 before report
replacement. Stored-run loading remains outside the POS validation error handler.

Convert any non-finite derived metric to the existing unavailable/null value.
Representable data with an unrepresentable ratio therefore remains usable,
and persisted JSON agrees with the API response. Other valid metrics are kept.
No arbitrary monetary cutoff or new currency conversion was introduced.

## Verification

- Six overflow patterns cover line multiplication, one receipt, multiple
  receipts, per-SKU/whole-dataset quantities and negative refund amounts.
- Every ordering of cancelling extreme sales/returns is rejected consistently.
- Very small quantity/price denominators produce null ratios and strict valid
  JSON. Large representable amounts, fractional goods, refunds, free products
  and ignored foreign SKUs retain their expected scores.
- 393 focused fidelity/analysis checks passed in 4.05 seconds. The seven final
  API checks passed again in 3.07 seconds after narrowing the error handler.
  Overflow uploads preserve prior JSON byte for byte; an unavailable ratio's
  saved report exactly matches the HTTP response.
- Pyright passed for both changed modules, including the final application
  adjustment. No frontend rebuild, full suite or paid model calls.
