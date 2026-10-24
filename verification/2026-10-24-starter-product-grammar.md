# Constrain the first automatic-product response

The initial rack/category request already had request-local identifier enums, but
its subsequent bulk product request still used unconstrained category and SKU
strings. A local grammar could therefore accept invented SKUs, products from a
different category, or up to sixteen products even when a category's available
shelf capacity was one. Runtime checks rejected these choices only afterward.

The primary ProductSelection schema now supplies one object alternative per
selected category: its category is constant, SKU strings come from that category's
actual currency-specific catalog, and the array size respects the category limit
and shelf capacity. The outer array has the expected group count. Existing runtime
validation still enforces unique categories/SKUs and exact coverage, which the
array grammar alone does not guarantee. Providers that ignore grammar retain the
same semantic correction and bounded per-category recovery behavior. No selection
is applied to the store during this stage.

Eighteen HTTP schema-contract regressions failed before implementation. Final
focused verification covered 706 passing tests: 84 grammar/recovery checks and
622 selection/placement/API controls; an updated concurrent-schema control also
passed. Strict Pyright reported zero errors. The HTTP tests validate the transmitted
schema with Draft 2020-12, reject cross-category/invented identifiers and invalid
group/product counts, and cover USD/KRW/JPY, category ordering, capacities of one
through twenty, successful cache reuse and unchanged input stores. Concurrent
requests retain their own category/SKU/capacity bindings. Existing corrections,
persistent failure bounds, placement exclusions and context decomposition passed.

The extra identifier grammar adds request schema data; large catalogs may still
need the existing input-context decomposition. This is a schema/transport contract
verification, not a live-model quality measurement. No live inference, paid provider
or model-weight download was used.
