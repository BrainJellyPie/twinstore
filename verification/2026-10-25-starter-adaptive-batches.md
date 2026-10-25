# Recover starter assignments below the eight-row batch size

The existing recovery replaced failed grouped rack IDs with ordered tasks of
up to eight rows. If a local model returned just one category for that task,
the wizard still failed immediately after structured retries, even though
single-row requests could be answered correctly. A nine-rack reproduction
stopped at the first eight-row recovery request.

Failed ordered tasks now halve their row count and retry the same unassigned
rows, stopping at a single row. The smaller cap carries forward within that
selection, avoiding repeated attempts at a size the model already failed.
Successfully assigned rows keep their categories. Each task still enforces
its exact count, catalog membership and the shared sixteen-category limit.
Only existing selection-format, truncation, semantic-selection and typed
context failures enter this path. Other provider failures propagate.

An irreducible failure returns no assignments, starts no product selection
and saves no partial project. This recovery can add calls: a persistently
invalid eight-row task can be tried at 8, 4, 2 and 1 rows, with the existing
attempt/correction limit at each size. Successful eight-row and normal grouped
requests keep their prior call counts. Failed schema/context responses are
not cached; valid recovered leaves remain reusable on a repeat request.

Thirty-two actual LiteLLM/Instructor HTTP cases cover both structured modes,
2/9/24/100 rack rows, models limited to one or three rows, short answers,
unknown categories, typed context rejection and truncated output. Checks
include unusual exact rack IDs, category-budget saturation, remaining rows,
SKU membership, source immutability, bounded calls and cache reuse. Four
controls propagate unrelated provider errors, and one control rejects a
late failed row after an earlier successful row. Before the fix, 33 cases
failed and the four provider controls passed in 8.29 seconds.

Wizard API coverage also includes cafe and hypermarket creation in USD, KRW
and JPY with a model that answers one row at a time. The focused engine/API
run passed 313 tests in 17.73 seconds and exposed one old assertion expecting
only the first failed batch. That assertion now checks the bounded
8/4/2/1 sequence and the unchanged no-project/no-generation behavior; its
rerun passed in 2.95 seconds. Thus 314 distinct checks passed, with no pytest
warnings. Full source Pyright reported zero errors and warnings.

Responses and context limits were scripted; no native inference, weight
downloads or paid model calls ran. These checks establish bounded recovery
for these responses, not the category suitability or failure frequency of
the user's real local model.
