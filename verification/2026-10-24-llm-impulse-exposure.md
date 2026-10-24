# Keep LLM impulse purchases within the actual exposure list

The third simulation stage instructed the model to use only products exposed
along the planned route, but execution accepted any SKU stocked anywhere in the
store. A scripted model could therefore create impulse revenue for a distant or
unseen product. Those purchases could also displace a visible product through
budget pruning or the pattern's purchase cap.

The engine now removes nonexistent impulse SKUs, then excludes purchases outside
the exact exposure list supplied to stage three, before merging and applying
budget/product limits. The trace retains the model response and reports
`dropped_unexposed_buys` separately from invalid catalog SKUs. Planned destinations
remain valid even when they require walking to a previously unseen product. No
new model call or retry is introduced. Exposure retains its existing SKU-level
semantics; this does not change how multiple placements of one SKU are selected.

Before repair, the new matrix had 28 failing cases and five passing controls.
After repair, 161 focused exposure, purchase-limit, action-boundary, budget,
offline-engine and perception/routing checks passed in 0.76 seconds. Two added
shared-store checks passed in 0.32 seconds, for 163 unique checks. They cover:

- Both route orderings and both exposure modes; correct, wrong, absent and
  out-of-grid model targets; retained normal exit and removed empty checkout.
- Existing unseen and invented products interleaved with valid visible products,
  verifying that neither consumes their budget or purchase allowance.
- Opposite faces, the visibility output cap, planned distant purchases and empty
  exposure skipping the third model call.
- Actual routing, execution, revenue and shared-store checkout metrics, preserved
  response traces and unchanged source stores.

Changed-engine strict Pyright reported zero errors. No live inference, downloaded
weights or paid calls were used; responses were scripted. These checks establish
the exposure constraint, not the realism of model purchasing preferences.
