# Customer XLSX evidence retains formula result integrity

The customer workbook reader checked structure and resource budgets but did not
use the existing streaming scanner's spreadsheet-error and formula-cache checks.
Pandas could turn those cells into blanks, allowing automatic product selection
and customer generation to proceed with incomplete evidence. Existing retained
uploads were also passed to retries without workbook preflight.

Customer workbooks now collect cell issues and reject errors or uncached formula
results on their declared worksheet parts. All sheets are customer evidence.
The existing scanner also detects missing array-formula children and trailing
array ranges. Cached zeros and explicit empty strings remain valid results.
Workbook byte and cell budgets retain their existing limits.

New-store preflight returns 400 before project creation or model work. Retained
XLSX retries return 409 before registering a generation or replacing customers,
even if an earlier automatic summary exists. They explain how to correct the
workbook and attach it to a new store. Valid retained workbooks are still queued
with their original bytes and filename.

## Evidence

- Fifteen cases failed before the fix: eleven new uploads and four legacy
  retained-upload retries. Seven cached-result controls passed already.
- Coverage includes headers, ordinary formulas, Excel error cells, cached error
  values, blank numeric caches, trailing formulas, later sheets, renamed worksheet
  parts, absent array children and array tails beyond populated rows.
- 110 focused checks passed in 5.45 seconds, including workbook structure/resource
  limits, customer-upload integrity and existing array-formula scanner checks.
- Two additional valid-retained-upload cases passed in 2.34 seconds: 112 distinct
  checks overall. They cover a cached zero and an explicitly empty array result,
  including an uppercase `.XLSX` filename.
- Strict Pyright: zero errors and warnings. Tests intercepted product selection
  and worker submission; no live model calls.

```sh
uv run pytest -q tests/server/test_customer_workbook_formulas.py tests/server/test_customer_workbook_preflight.py tests/server/test_customer_upload_retry_integrity.py tests/server/test_workbook_resource_boundaries.py tests/engine/test_pos_array_formula_cells.py --tb=short
uv run pyright src/
uv run pytest -q tests/server/test_customer_workbook_formulas.py -k retained_cached --tb=short
```
