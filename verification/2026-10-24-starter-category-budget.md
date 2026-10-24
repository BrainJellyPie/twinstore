# Keep small starter tasks within the global category budget

The fallback for models that invent rack identifiers uses ordered batches of up
to eight rack rows. Its local schema allows one catalog category per row, while
the whole store allows at most sixteen categories. With 9–15 categories already
selected, eight new valid choices could exceed that global cap. Repeating the
answer during semantic correction then aborted automatic starter selection even
though all selected catalog IDs were valid.

Before the budget is full, each task now contains at most the number of remaining
new-category slots. Every row can then choose a different new category without
exceeding sixteen. Once sixteen categories are selected, the existing restriction
to those categories applies and eight-row tasks resume. The cursor advances by
the actual batch size, preserving all rack rows and their original identifiers.
Unknown/duplicate IDs, response lengths, capacity, product checks and bounded
provider-error handling remain unchanged. Near the limit this may use a smaller
task and an additional request; it does not increase retry limits.

The corrected pre-fix test run had 18 failures and six passing controls. Twenty-four
HTTP cases cover both structured modes; 17, 24, 99 and 100 rack rows; and cumulative
category counts of 9, 11 and 15 before the next task. They deliberately start with
the originally reported invented-section-ID response and exercise fallback through
final product selection. Assertions cover exactly-once rack assignments, catalog
SKU membership, the global cap, no semantic retry on small tasks, full cache reuse,
and no mutation of the source store.

Focused starter selection, repair, decomposition, context and grammar checks:
638 passed in 7.35 seconds. Strict Pyright: zero errors. All model responses were
scripted; no live inference was used.
