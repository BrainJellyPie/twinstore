# Preserve usual prices through Excel product edits

Product workbook export omitted `SlotItem.regular_price`, and the slot upload
schema and reconstruction also discarded it. A product selling for 2500 with a
usual price of 5000 came back with a usual price of zero. That removes the price
comparison used by shelf labels and the rule engine's price response.

Exports now carry `regular_price (minor units)`. The parser validates whole,
nonnegative, browser-safe values, and the upload API passes the field through to
saved slot items. Zero remains the explicit no-reference value. Legacy workbooks
without the column retain their previous behavior: no separate reference price.
The parser also accepts the `regular_price` and `regular_price (cents)` headers.

## Verification

- USD, KRW and JPY export/import round trips retain 2500/5000 price pairs.
- Zero, blank, numeric text, maximum safe integers, header variants, invalid
  strings, infinities, fractions, negatives, booleans and unsafe integers.
- API persistence of ordinary and zero reference prices; invalid reference prices
  reject the request without replacing saved products. Existing concurrent slot
  import tests remain passing.
- Baseline: 7 API failures and 10 workbook failures reproduced the missing field
  and the absence of validation.
- Focused backend: 21 passed in 5.34 seconds. Frontend: 31 passed in 0.741 seconds.
- Changed backend modules pass Pyright; frontend TypeScript and targeted ESLint
  pass. Production build succeeds in 17.63 seconds with existing bundle-size and
  Babel timing warnings. No model calls.
