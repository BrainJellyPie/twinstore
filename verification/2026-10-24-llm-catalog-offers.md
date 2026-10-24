# Keep the model's chosen offer through execution

Compact catalog codes distinguish SKU/name/price/promotion combinations, but their
response validator reduced every code to a SKU before caching. When one SKU had
multiple offers, routing could then select another price or shelf level. A
scripted model choosing two 700-unit items could produce a 200-unit checkout
instead of 1,400. The same loss could admit an impulse purchase that exceeded its
budget, or misstate stockout revenue.

Action responses now retain their original offer codes in the cache. A versioned
schema comment separates these from old canonical-only entries, which no longer
contain enough information to recover the selection. After validation and removal
of model-supplied internal hints, the engine binds a code to a real matching offer
and sets its canonical SKU, stance, face, block and level. Among identical repeated
offers, the existing target/face preference still applies. Canonical SKUs returned
by non-grammar providers keep their previous placement rules.

Locked, blocked, off-grid or unrepresentable selected placements are not replaced
with another price; the existing invalid-buy guard drops their codes. Normal route
reachability checks still apply. No store data or raw cached response is mutated.
This applies to full and context-recovered intent and to impulse decisions.

Twenty of the original 24 HTTP regressions failed before the fix; four order
controls already selected the intended level by chance. Coverage includes both
JSON modes, both route orderings, reversed shelf order, repeated SKUs across
levels/blocks/racks, injected internal hints, preserved two-unit purchases,
checkout, cache reuse and stockout loss. Additional cases verify impulse-budget
rejection at 500 versus acceptance at 1,400/unlimited, unavailable placements,
repeated identical offers and migration from old canonical-only cache records.

Focused verification passed 293 unique tests: 274 client/engine/catalog/recovery
checks in 7.21 seconds; 64 offer/routing checks in 3.96 seconds (47 overlap); and
two additional cache migration checks. Strict Pyright reported zero errors.
Eight existing LiteLLM logging-cleanup warnings occurred in the broad focused run.
All model responses/transports were scripted; no live or paid inference was used.
