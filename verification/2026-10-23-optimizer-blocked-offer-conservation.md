# Optimizer unreachable-offer conservation

The feasibility check allowed any SKU already present on a blocked face to appear
on additional blocked faces. A baseline with A on both an inaccessible north face
and an accessible south face accepted a swap of the last reachable A with blocked
B. The optimized shelf then sold only B: A disappeared from the reachable catalog
without violating the SKU whitelist.

The baseline allowance now counts exact blocked SlotItem values rather than SKU
membership. Candidate blocked counts must be a sub-multiset of those baseline
counts. Price, name, reference price, promotion and image reference participate,
so restoring one offer does not permit hiding another offer of the same SKU.
The existing `blocked_skus` helper retains its public behavior.

Unchanged baseline warnings remain acceptable. Moving formerly blocked stock to
reachable faces and rearranging already-blocked stock with the same offer counts
remain allowed. This preserves a minimum relative to the baseline, not every
temporary accessibility improvement during the search. Existing saved optimizer
results are not rewritten.

Verification:

- Corrected reproduction fixture: 15 failed and 2 passed in 0.30 seconds before
  the fix. An initial fixture syntax error was resolved before this reproduction.
- 27 focused optimizer-move tests passed in 1.17 seconds; 6 unrelated full-search
  and evaluator cases were deselected. Includes actual move rejection/input
  immutability, 9 multiplicity boundaries, 5 same-SKU metadata differences,
  unchanged/improved accessibility, blocked/reachable rearrangements, existing
  random moves, replay, locked fixtures and orientation constraints.
- Pyright on the changed move module: zero errors or warnings.
- No live models, full optimization runs or frontend build.
