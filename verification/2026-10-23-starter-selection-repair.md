# Automatic starter selection: incomplete model responses

The reported wizard error occurred before customer generation: automatic product selection accepted a
schema-valid category response, then immediately failed if one empty shelf section was missing or
duplicated. There was no opportunity to correct the selection. When caching is enabled, repeating the
same prompt can also retrieve the same invalid response.

Each selection stage now validates its complete answer and permits one corrective request containing
the original constraints, previous response and precise missing/unknown/repeated identifiers or capacity
limit. Category correction completes before product selection begins. The second invalid answer still
fails; no product choice or excluded category is silently substituted. The existing model client's
structured-output retry budget is two attempts per request. Provider exceptions are not retried by
the semantic-correction loop. Successful first answers still require two selection calls total.

Coverage includes:

- Eleven response mutations: missing/unknown/repeated shelves or categories, missing/repeated product
  categories, unknown/wrong-category/repeated SKUs and excessive product counts; both recoverable and
  persistent errors, with USD/KRW/JPY catalog values.
- Forty-eight reproducible generated combinations (seed 261023) of 1, 2, 15, 16, 99 or 100 sections,
  mixed shelf/fridge types, blocked/occupied shelves, Unicode names, 1–4 products per slot, category
  exclusions and assortment limits. Every eligible section must be assigned once.
- Wizard creation for pharmacy, cafe and hypermarket formats in all three currencies; no partial
  project/customer job on persistent failure; existing-layout preview/save preserving stocked shelves;
  source changes during correction; and real response-cache behavior with the provider replaced offline.

Results:

- Before the fix: **45 failed, 2 passed in 1.19 s** in the new correction tests.
- Engine selection checks: **529 passed in 1.56 s**.
- Additional wizard/starter/template/cache checks: **373 passed, 1 failed in 24.48 s**. The failing new
  test changed only a layout-list label, which intentionally does not invalidate the product snapshot.
  Correcting it to change the store input verified the intended stale-source rejection; the targeted
  rerun passed. No production change was made for that test assumption.
- Strict Pyright on `engine/starter_selection.py`: **0 errors, 0 warnings**; `git diff --check` clean.

All model responses were offline doubles; the cache test uses the actual client cache with its provider
call replaced. Tests demonstrate recovery when a model supplies a valid correction, not a guarantee that
every live model will correct itself. No frontend or full-suite rerun was needed.

```bash
# From backend/
.venv/bin/pytest -q tests/engine/test_starter_selection_repair.py tests/engine/test_starter_selection.py --tb=short
.venv/bin/pytest -q tests/server/test_starter_selection_repair_api.py tests/server/test_project_templates.py tests/server/test_starter_fill_api.py tests/engine/test_initial_assortment.py tests/engine/test_starter_selection_repair.py::test_cached_incomplete_answer_does_not_trap_retries --tb=short
.venv/bin/pytest -q 'tests/server/test_starter_selection_repair_api.py::test_existing_layout_repair_preserves_source_and_rechecks_changes[True]' --tb=short
.venv/bin/pyright src/store_emulator/engine/starter_selection.py
```

This is a main-branch fix after v0.4.11. The published v0.4.11 binaries are unchanged.
