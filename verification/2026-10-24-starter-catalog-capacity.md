# Bound assortment requests by the actual catalog

The product request ceiling included shelf capacity, the user limit and the global
sixteen-product limit, but omitted the number of distinct products in the supplied
category. Most current categories contain fewer than sixteen products. A model
trying to fill the advertised allowance could repeat valid IDs, then fail duplicate
validation both in the bulk selection and its single-category fallback.

The shared per-category ceiling now also includes the distinct candidate SKU count.
Both prompt payloads and output grammars already derive their limits from that
value, so they stay consistent. User limits and small shelf capacities still take
precedence. Catalog prices, ordering, SKU identities, duplicate validation and
retry counts are unchanged; no product is substituted or invented.

Before the patch, 24 scripted regressions failed and 24 smaller-limit controls
passed. Final coverage includes six-, eight- and larger product lists, a catalog
containing five copies of one identity, USD/KRW/JPY, user limits of three or sixteen,
and bulk versus fallback selection. Actual deterministic shelf filling checks
distinct selected SKUs, placement membership, absence of within-slot duplicates
and preservation of the original store. Existing HTTP product-grammar checks cover
the transmitted per-category constraints and tighter shelf-capacity limits.

Focused assortment, repair, small-task and grammar checks: 197 passed in 5.28 seconds.
Strict Pyright: zero errors. Responses were scripted; no live inference was used.
