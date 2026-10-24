# Connect dense floor-plan aisles without deleting their contents

Valid model coordinates could produce disconnected aisles after grid mapping.
Repair stopped after forty tile removals and reported successful clearance even
when route errors remained, so import subsequently failed. Raising that limit
alone was insufficient: the existing strategy deleted unreachable shelves
behind an intact barrier. An eight-row example lost 126 of 128 product tiles
and still had inaccessible stocked faces.

Use a 0–1 breadth-first search from the entrance: walking across floor costs
zero, removing a product tile costs one, and counters cannot be crossed or
removed. Open a least-cost path to another disconnected floor region and repeat.
This chooses a short opening at each step, not a globally optimal set of removals.
Every iteration removes at least one product tile, bounded by the original
grid's product count. Gates, counters, retained merchandise and source readings
are preserved. Existing clearance notes report the actual removed tile count.

The final eight-row example retains 120 tiles after eight removals; eight
columns retain 119 after seven. Checkerboard and seeded irregular arrangements
also finish with zero route errors and zero blocked-stock warnings, retaining
42 and 80 product tiles respectively. These were scripted model responses,
not claims about the recognition quality of any native model.

Eight HTTP cases failed on the original forty-removal limit. The preservation
checks also reproduced excessive deletion and blocked faces when only that
limit was increased. Both JSON modes cover model parsing, store construction,
source immutability and repeat construction from cached responses.

After the final fix, 165 focused floor-plan reading, geometry, API and persistence
checks passed in 9.85 seconds; another 48 grid-boundary cases passed in 2.24
seconds. Those cross 8×8, 16×16 and 16×8 grids, four density levels and all
entrance corners, with a fixed checkout. Pyright reported zero errors and
warnings. The 34 pytest warnings are existing async logging cleanup warnings.
No real model inference or downloaded model was used.
