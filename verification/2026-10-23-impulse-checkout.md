# Impulse-only baskets go through checkout

The pattern–intent–impulse engine asks stage 2 to omit payment for a browsing-only
visit, then asks stage 3 to return only extra browsing/purchase actions. When
stage 3 added the first purchase, the merged visit therefore had a basket but no
payment. Revenue was counted while checkout service, waits and abandonment were
skipped. The same omission could occur when a model forgot payment for a planned
purchase.

After invalid products and over-budget impulse purchases are removed, the engine
now adds one payment before exit if purchases remain, no payment exists, and the
layout has a counter. Existing payment destinations/durations are preserved.
The ordinary route sanitizer chooses a counter service tile for the fallback;
its nominal 15-second dwell is bounded by the counter's limits, and shared-store
runs apply their configured checkout times. Counterless layouts retain their
existing behavior rather than inventing a payment location.

Focused verification:

- Before the fix: **6 failed, 16 passed**, 0.31 seconds, using scripted model
  responses. Both route orderings omitted payment and counted two simultaneous
  impulse-only baskets as revenue even when one should abandon a busy till.
- After the fix and counterless boundary coverage: **219 passed**, 0.93 seconds.
  The new 24 cases cover impulse/planned purchases, no purchase, invalid SKU,
  budget removal, an existing checkout, counterless layouts and queue abandonment.
  Existing model, budget, selected-offer and routing checks also pass.
- Strict type check of the changed engine module: **zero errors/warnings**.

No live models or real data were used; frontend source is unchanged. This is a
follow-up to the fixed v0.4.11 snapshot, with focused checks instead of repeating
the release's full backend suite.
