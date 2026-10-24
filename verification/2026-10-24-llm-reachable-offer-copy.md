# Resolve repeated offers inside the shopper's reachable area

Offer decoding previously filtered locked or non-walkable shelf faces but did not
check connectivity from the shopper's entrance. It could bind to an identical
offer across a partition and lose the purchase even when a reachable copy was in
stock. Which rack appeared first, or an inaccessible target suggested by the model,
could therefore change sales without changing the available products.

When the engine supplies its pathfinder, decoding now filters placements by the
shopper's actual reachable area before resolving the preferred target. Results are
memoized per stance. The fallback must match SKU, name, price and promotion exactly.
A canonical SKU first resolves its legacy offer by target/face, then only identical
copies of that offer may replace an inaccessible placement. Impulse placements
remain restricted to the exposed anchors. Direct decoder callers without a
pathfinder retain their previous behavior, and cached raw references remain valid.

The pre-fix run failed 24 cases with 72 controls passing. The 96-case matrix uses
valid multi-entrance layouts and covers either side of the partition, transposed
coordinates, rack ordering, absent/local/remote target hints, codes/canonical SKUs,
and identical versus differently priced offers. It verifies the exact purchased
placement and price, rejection rather than substitution of a different offer,
drop counts, exit and source-layout immutability.

Focused reachability, budget/line limits, offer identity, exposed placement,
structured HTTP/cache boundaries and internal-field protection checks: 452 passed
in 8.32 seconds. Nine existing LiteLLM logging-cleanup warnings occurred. Strict
Pyright: zero errors. Responses were scripted; no live inference was used.
