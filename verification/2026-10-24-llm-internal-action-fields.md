# Exclude internal placement fields from generated shopping actions

`CustomerAction` hides `origin`, `product_block` and `product_level` from its JSON
schema using `SkipJsonSchema`, but Pydantic still accepts and validates them.
Models that emitted those fields could therefore change the selected offer and
price. An otherwise identical three-unit purchase changed from 300 to 2,700
when the response included another shelf level. A string such as `"eye level"`
instead failed validation of the whole response.

The intent response now strips those engine-only fields before validating its
actions. The structurally identical impulse response inherits the same boundary.
Raw action dictionaries and supplied `CustomerAction` instances are copied, so
caller-owned values remain unchanged. All public action fields still validate
normally. Routing assigns the actual placement later, and the engine assigns
planned/impulse origin. Direct domain actions and rule/VLM offer selection retain
their internal hints. Existing cache reads apply the response validation too.

Before repair, 30 new cases failed and six controls passed. After repair, 206
focused action-boundary, product-limit, exposure, selected-offer, offline-engine
and budget checks passed in 1.04 seconds. Eight HTTP/cache cases passed in 2.45
seconds, for 214 unique checks. Coverage includes both model stages and route
orderings; valid conflicting block/level hints; malformed strings, lists, objects
and nulls; actual purchase values, quantity and attribution; source immutability;
preserved legitimate domain offers; JSON and JSON-schema modes; and old cache
entries containing hidden hints. HTTP cases use the real OpenAI/LiteLLM/Instructor
stack with a mock transport and require only one server request plus a cache hit.

Strict Pyright for the full three-stage engine package reported zero errors.
Seven existing LiteLLM asynchronous logging cleanup warnings occurred in the
HTTP tests. No live inference, downloaded weights or paid calls were used.
