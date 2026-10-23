# Displaced product access during moves

Marketing variants and natural-language layout edits shared a move operation that
checked destination access but always chose the first source occurrence. If that
source faced a wall and the destination was full, the displaced destination
product was swapped into the wall. A reproduced move reported success without
warnings while removing F from the reachable assortment (A/C/D/E/F became A/C/D/E),
even though another accessible source A was available.

Full destinations now require a reachable source to receive the displaced item.
If none exists, that slot remains unchanged with a warning; later destination
blocks are still considered. Moving a blocked source into available space remains
valid. New destination slots are attached only after a product actually moves,
so missing/already-placed products do not leave empty slots behind.

Verification:

- Baseline: 5 failed and 3 passed in 0.76 seconds.
- 31 move and related marketing tests passed in 4.96 seconds. Covers source order,
  full destinations with and without accessible sources, new/existing free space,
  mixed full/empty blocks, unknown/already-placed products, input immutability,
  existing unreachable-destination checks and layout-edit integration.
- Pyright on the changed variants module: zero errors/warnings.
- No live model calls, broad suite or frontend build.
