# Exact offer names in vision-shopper baskets

The vision engine previously rebuilt its basket names by searching the whole
catalog for each chosen SKU. When one SKU had differently named offers, a
purchase of Premium tea was described to the next model call as both Basic tea
and Premium tea, including variants on an unvisited rack. The purchase event
and price were already correct; the context for subsequent choices was wrong.

Twelve scripted HTTP cases reproduced the error in 2.88 seconds: JSON and
JSON-schema modes, planned and prior impulse purchases, and aliases on another
block, another shelf level or a distant rack. The fixture fixes the intended
plan; exposure, shelf rendering, HTTP response parsing, impulse resolution,
routing and final purchase execution run through the application engine.
No real model inference or paid API calls are used.

Basket names now come from the actual planned and earlier impulse buy actions.
The existing placement resolver retains each action's target, face, block and
level; browse actions do not become basket entries. Names remain unique.

The expanded 24-case regression also covers same-name offers with different
prices. It verifies the chosen 700-unit offer, the completed purchase and exit,
and the exact basket sent to the next shelf glance. All 87 focused basket,
offer-disambiguation, glance and badge-grammar tests passed in 30.76 seconds.
Six existing LiteLLM async-logging cleanup warnings were reported.
Strict backend type checking passed with zero errors; `git diff --check` is clean.
