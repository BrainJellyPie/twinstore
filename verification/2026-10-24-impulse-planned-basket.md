# Give impulse decisions the actual planned basket

The impulse prompt previously described planned events only by action label and
free-text narration. With empty narration, buying different products, quantities
or prices produced the same prompt. When exposure and pattern limits matched,
the response cache reused the first basket's impulse answer for the changed basket.
Twelve HTTP cases reproduced this behavior using different stage-two pattern
grammars while holding the shopper, seed and exposed products constant.

Buy events now include compact JSON facts resolved from the engine's exact selected
placement: SKU, name, quantity after the configured per-line clamp, unit price,
line total, currency and any promotion. Narration remains separate. These facts
give the model its existing basket and distinguish cache identities without extra
model calls. Exposure lists and purchase execution are unchanged.

138 distinct focused checks pass: 111 related HTTP/cache/exposure/budget/checkout
checks in 6.32 seconds, plus 27 quantity/currency/promotion boundary checks (39
including the repeated regression cases in 3.44 seconds). The HTTP matrix covers
both structured modes, both ordering modes, product changes, quantity changes and
different offers sharing one SKU. Additional checks compare the prompt facts with
executed quantities/spend for zero, one and oversized quantities, configured caps
1/2/6, USD/KRW/JPY, and quoted/non-ASCII names and promotions. Store inputs remain
unchanged and repeated identical baskets use cache. Strict Pyright: zero errors.

All model responses were scripted. The prompt grows by one compact fact object
per planned buy; no live inference or universal context-capacity claim is made.
