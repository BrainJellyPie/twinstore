# Preserve shopper intent across catalogs with local IDs

A grocery shopper reordering Milk 1L (p013) rated Laptop Privacy Cover 3pk in the
electronics catalog (also p013) as an exact match with relevance 1.0. Search
arrivals also used the unrelated ID. Product IDs were scoped to each store, but
paired runs passed the control store's targets unchanged to all variants.

Before each variant, bind category targets by full case-insensitive names and
product targets by SKU when present, otherwise full product and category identity.
Prefer an identity-matching original ID; use a unique relocated match otherwise.
Missing or ambiguous products keep a nonempty target absent from that catalog,
preserving the existing specific-unavailable-product behavior instead of turning
the shopper into a generic buyer. Collision-safe absent IDs never select a real
product. A matched SKU may retain its product identity through a name change.

Original shopper snapshots, goals, budgets, IDs, missions, accessibility, arrival
source and random seeds are unchanged. Only the per-variant routing targets differ.
The run's original shared shopper record remains the record of its initial intent.

Initial valid baseline: six failures and two passes in 2.42 seconds (the test
request's click limit was first corrected to the API's existing minimum of three).
Final coverage includes clones, moved IDs, unavailable products, renamed SKUs,
ambiguous names, category changes, misleading shared IDs, conflicting SKUs, absent-ID
collisions and direct/search arrivals, plus the real grocery/electronics example.
26 integration tests passed in 9.35 seconds; the expanded 19-case target matrix
passed in 2.76 seconds (37 distinct tests overall). Full-source Pyright reported
zero errors and warnings after explicitly typing the variant shopper list; backend
boot passed. No frontend runtime or real model service was used.
