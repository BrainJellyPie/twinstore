# Preserve unique products when importing physical shelves

The generated station-kiosk layout has 89 unique SKUs, but importing it created
127 online product rows. A specialty cafe similarly produced 112 rows for 90
SKUs. The importer filtered already-seen SKUs before processing each whole rack,
so repeated placements within that rack all passed the filter. This inflated
the assortment and the shopper sampling pool.

The importer now also checks the seen set as each item is processed. It follows
its existing documented contract: one product per SKU, using the first shelf
placement's name, price, reference price, image and category. Distinct SKUs with
identical labels remain distinct, and source layouts are not modified.

Engine regressions reproduced **24 failures with 4 passing controls** across
three generated layouts and USD/KRW/JPY, repeated levels/faces/blocks/slots/racks,
and differing later offers. The real import API reproduced another **3 failures**
after correcting the test to fetch the full setup rather than its generation
summary. The invalid summary fixture was not a product finding.

After repair, the new engine/API cases plus existing online API and currency
comparison regressions passed: **44 tests in 6.46 seconds**. Full-source Pyright:
**0 errors, 0 warnings**. No paid or native model calls were made.

Existing saved online catalogs are not rewritten; newly imported catalogs use
the corrected SKU selection.
