# Payment routing preserves the chosen checkout

PAY normalization returned the first counter's service tile before checking
whether a later counter matched the requested destination. In a generated
three-counter store, requests for (3, 6) and (4, 6) both walked to (2, 6).
Timeline attribution could also name an adjacent shelf when its access tile
overlapped the selected checkout, depending on the rack list order.

Routing now checks all counters for the selected service tile or counter body
before falling back to the first usable counter. Payment attribution uses the
service counter at the shopper's reached position, preserving its identity and
dwell limits when a shelf shares that tile. Invalid destinations retain the
existing service-tile fallback. This does not change shared-store queue
allocation or resolve ties between multiple counters sharing one service tile.

Focused offline verification:

- Before the fix: **36 failed / 13 passed**, 0.77 seconds.
- After the fix: **1,283 passed**, 15.55 seconds across routing, shared-store
  queues/stock, selected offers and checkout clearance.
- Forty-nine new cases cover three counters, four wall orientations, body and
  service targets, reversed rack order, preserved input and invalid fallback.
- Strict backend types: **zero errors/warnings**.

No live models or real project data were used. Frontend source is unchanged;
full suites were not repeated under the user's focused-validation policy.
