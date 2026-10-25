# Match staff-script drafting to the product offer being tested

Staff-script tests already reject a SKU with conflicting names, prices or
promotions across shelves. Automatic script drafting instead selected its first
placement. Reordering shelves could change the price or promotion given to the
writer, producing an apparently usable script for a test that cannot run.

Drafting now checks the same offer fields before constructing or calling the
model client. Conflicts return an actionable HTTP 400. Identical repeated
placements and other SKUs remain supported; the source layout is unchanged.

Twenty API regression cases cover name, price and promotion conflicts, identical
repeat placements, an unrelated SKU, USD/KRW, and reversed shelf order. The price
case includes a free offer versus a paid offer. Valid cases retain the exact
formatted price and promotion; conflicts make zero client-construction and
model calls. The currency fixtures use matching project and layout currencies.

Before repair: 12 failed, 8 passed in 3.56 seconds. After repair: 67 focused
script drafting, paired-test API, distinct-script and engine tests pass in 4.48
seconds without warnings. Full-source Pyright reports zero errors and warnings.
No full suite, paid calls, model weights or native inference were used.
