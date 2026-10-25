# Keep product identities separate in the analyst's fact sheet

Run commentary grouped purchases by their display names. Distinct SKUs both
named Milk became one product's units, revenue and impulse units; conversely,
one SKU with different recorded names became multiple products. The model and
its cited figures therefore received incorrect product-level aggregates even
though overall revenue remained correct.

Product aggregates now use the exact SKU. Name-only legacy events use a
separate name identity so they cannot collide with a real SKU of the same text.
Identical display names include their SKU in the fact-sheet label, or state
that the SKU is unavailable for legacy rows. Unique names keep their existing
readable labels. Revenue ordering and overall totals remain unchanged.

Twelve HTTP cases cover two output modes, USD/KRW, distinct SKUs, case-sensitive
SKU pairs and a real-SKU/name-only collision. They exercise real LiteLLM and
Instructor with scripted replies, validate separate units/revenue/impulse units,
reject the obsolete merged citation, and check cache and source immutability.
Controls retain readable unique names, aggregate renamed records of one SKU,
and preserve name-only legacy aggregation. The API test checks the public fact
sheet and saved/reloaded answer citations.

Before the repair, 14 cases failed and seven passed in 11.66 seconds. Focused
identity, annotation, API, locking and project-lifecycle suites passed 84 checks
in 8.52 seconds, with 39 known LiteLLM logging-cleanup warnings. Full source
Pyright reported zero errors and warnings. No native model inference, model
downloads or paid calls were used.
