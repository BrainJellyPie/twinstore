# Purchases resolve the reached shelf face

The SKU lookup kept only the first matching slot on each rack. When a product
appeared on several faces, both routing and timeline construction selected that
first slot even when the shopper stood at another face. This changed the route,
price and stock pool. In the reproduction, four shoppers each approached a
different stocked face, but only one could buy; the other three were reported
as stockouts. Reversing slot order changed which price was used.

The lookup now retains all matching slots. Resolution first matches the supplied
face and actual stance, then a placement visible from the stance when the face
is missing or wrong. Existing rack-only and first-placement fallbacks remain
available for actions that routing must relocate.

Focused verification, without model calls:

- Before the fix: **20 failed / 6 passed**, 0.62 seconds.
- Routing and shared-store regressions: **605 passed**, 5.49 seconds.
- The 26 new cases cover all four faces, both slot orders, correct/missing/wrong
  face hints, route sanitation, actual timeline prices and independent face
  stock. After adding route assertions: **26 passed**, 0.23 seconds.
- Strict backend types: **zero errors/warnings**.
- The four-face replay now sells all four units for the correct total of 1,000
  minor currency units, without false lost units/revenue.

Frontend source is unchanged. Full suites were not repeated, following the
user's request to spend roughly 90% of effort on finding/fixing bugs and 10% on
focused verification. This change does not alter same-face shelf-level price
selection or general multi-cell routing.
