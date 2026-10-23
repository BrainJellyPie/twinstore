# Repeated-product compliance findings

An unchanged A–B–A–C shelf was reported as misplaced: captured products were
deduplicated globally while reference products retained repeated runs, making C
look like position 3 instead of 4. Repeated reference runs also duplicated missing
and facing-count findings. Price checks selected one reference price and the first
captured tag, producing false findings for legitimate multiple prices while
missing later erroneous tags and all errors against a zero-price reference.

Both sequences now collapse only adjacent facings and retain later occurrences.
Each SKU's complete position list is compared once. Missing facings are totaled
across its reference runs and quantity findings are emitted once per SKU/level.
All non-estimated, read tag prices are checked; a mismatch is grouped by observed
price and its box contains only the corresponding photographed products.

Price checks use the set of valid reference prices for that SKU on that level,
preserving the existing tolerance of one minor unit or two percent. They do not
infer which identical-SKU offer a tag belongs to when several reference prices
are valid, or detect a swap of those valid prices between identical products.
Unread/estimated prices remain excluded. Compliance score still measures facing
counts on each level; order and price deviations are separate findings.

Verification:

- Baseline: 55 failed and 119 passed in 0.63 seconds.
- 203 focused tests passed in 6.52 seconds, including 162 unchanged four-position
  layouts (all sequences of 3 SKUs, with equal or varied prices), repeated-product
  movements, missing/reduced repeated products, an erroneous first/middle/last
  price tag, zero-price references, unread/estimated prices and split captures.
- Pyright on the changed audit module: zero errors/warnings.
- No live model calls, full-suite run or frontend build.
