# Do not save an earlier price beneath an invalid amount draft

The online designer marked malformed amounts as invalid, but its save buttons
remained enabled and sent the last valid numeric value. Hiding a product with
the filter also unmounted the amount input and discarded its unfinished text.

Amount text now belongs to the designer draft, keyed by the option or product ID
and price field. Either save action is disabled until all edited amounts are
valid. Filtering preserves both the text and the error; correcting one field
does not clear another field's error. Zero is a valid amount.

Before repair: **11 UI regressions failed, 4 controls passed**. Coverage includes
empty/text/negative/grouping/exponent/unsafe-integer inputs, product and reference
prices, delivery/service fees, the free-delivery threshold, filtering and
multiple simultaneous errors. After repair, **51 focused frontend tests passed
in 3.91 seconds**, including online browser and currency-formatting controls.
TypeScript and changed-file ESLint passed with no diagnostics; the production
build passed with the existing bundle-size/plugin timing warnings. Backend
checks were not repeated because this change only touches frontend behavior.
