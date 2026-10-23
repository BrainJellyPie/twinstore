# Captured facing distribution across racks

New-rack placement assigned an entire recognized product group to the column of
its center. A photograph containing twelve consecutive facings of one product
created three racks but stocked only four facings on the middle one; the outer
racks remained empty despite enough total capacity.

Column splitting now assigns each observed facing box by its center. When a
reviewed facing count differs from the number of boxes, integer largest-remainder
allocation preserves the declared total across the observed positions. Existing
per-rack capacities still apply afterward. Product IDs remain stable across parts,
so reports count each original group once and mark it dropped only if no part is
placed. Partial losses remain reflected in the reduced-facing count.

This does not invent positions for products lacking boxes, enlarge rack limits,
or guarantee full retention where observed density exceeds a column's capacity.
Existing reduced-facing acknowledgement remains required for actual losses.

Verification:

- Initial focused reproduction: 37 failed and 5 passed in 0.60 seconds.
- Related 90-case engine/API run: 89 passed in 6.71 seconds; one old expectation
  assumed the previous loss of 20 facings. With two observed positions, 8 of that
  photo's 24 reviewed facings now fit, plus 2 from the other photo: 10 placed and
  16 reduced. The updated acknowledgement test passed in 3.34 seconds.
- A new API case retained all 12 facings plus 2 from another photo through preview
  and save, without a reduction acknowledgement. Original product count stayed 2.
- Final 45 focused cases passed in 3.32 seconds after report-count coverage was
  added (92 unique related cases covered overall). Includes counts 5–16, multiple
  product runs crossing boundaries, 25 reviewed-count/box-count combinations,
  24→16 true capacity reduction and a partially retained group.
- Pyright on the changed planogram module passed. No live model calls or frontend
  build were needed.
