# Ambiguous POS headers

## Failure and change

`receipt_id,sku,sku,quantity,unit_price` with product values `tea,coffee`
previously imported `tea`. Changing the second heading to `SKU` or ` sku `
imported `coffee`. Pandas renamed exact duplicates, while later normalization
silently chose the last case/space variant. Repeated receipt, amount, clock and
store/register headers had the same ambiguity.

Read the header as an ordinary first row so its original names survive. Reject
duplicate recognized names after normalization, including punctuation variants
of the same receipt-scope field. Process the remaining rows as positional cell
tuples, preserving identifier text and avoiding duplicate-name dictionary
warnings. Existing CSV table and XLSX archive/range budget checks still run
before dataframe allocation.

Distinct aliases such as `sku` and `barcode` retain their existing documented
priority because real exports can contain both different identifiers. Repeated
unknown notes/spacer columns remain ignored. Empty optional values, explicit
zero prices/quantities, fractional quantities and refund semantics are unchanged.

## Verification

- Baseline: 68 failures and 6 valid controls in 0.98 seconds.
- Both CSV and XLSX: exact/case/space duplicates of ten recognized fields,
  punctuation variants of store IDs, distinct alias precedence, duplicated
  ignored notes/blank columns, textual IDs and header-only inputs.
- 437 focused parsing/calendar/receipt-scope/numeric/budget checks passed in
  2.47 seconds.
- Four API checks passed in 3.65 seconds: HTTP 400 before store analysis for
  ambiguous SKU/scope columns in both formats; existing fidelity JSON retained
  byte for byte.
- Changed-module Pyright passed after explicitly treating pandas tuple cells
  as untrusted objects. No new `Any` types.
- No frontend rebuild, full suite or paid model calls.
