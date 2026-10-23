# Shelf photo offer matching

Photo views collapsed every occurrence of a SKU onto its first rendered mark.
With Tea priced at 100 minor units on level 1 and 700 on level 2, the rendered
view retained both offers, but both photo tags showed 700 and the photo response
lookup exposed only level 2. Changing the mark seed could change which price
was used. This distorted the visual stimulus and shelf-level summaries.

Photo marks now match the full rendered offer: SKU, display name, price and
normalized shelf level. Identical facings of that same offer still share a
representative badge. Matching uses the same price/name/level normalization as
capture-to-planogram conversion. Offers that do not fit are not relabeled with
another offer's badge, and their count reaches the existing report warning even
when their SKU occurs elsewhere in the twin.

This keeps SKU-level agreement unchanged in definition. An untagged photograph
still relies on the returned name; it cannot reliably identify which placement
of an identical product the respondent meant.

Offline verification:

- Initial reproduction: 49 failed, 4 passed in 3.19 seconds.
- 88 related engine/API cases passed in 12.19 seconds after offer matching.
- Added overflow coverage: 40 different prices of one SKU exceed the 32-offer
  row capacity; the 8 omitted offers retain no misleading badges and are counted.
  All 54 offer tests plus 4 terminal-job API cases passed in 6.12 seconds after
  adding that report count (89 unique relevant cases overall).
- Includes 4 mark seeds, free/equal/different prices, same/different heights,
  repeated facings, actual tag text, and 16 seeded catalogs with 256 captured
  products combining duplicate SKUs, names, prices and levels.
- Pyright passed on the changed engine and application modules.

No live model calls or frontend build were needed.
