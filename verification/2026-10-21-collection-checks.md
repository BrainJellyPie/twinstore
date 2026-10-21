# Field pilot collection checks — verification

Verified on 2026-10-21 on `feat/operator-modules`, preserving operator modules through `e1814e6` and the
staff-script evaluation introduced in `f3c7905`. Integrated development heads: `feat/vision-lab` and
`fix/edge-case-loop-20261021` at `6ab8a65`, `feat/store-scenarios` at `fe28be8`, and `feat/parastore-v3` at
`f41f326`. Each is an ancestor of the tested tree. The operator remote remained at `e1814e6` on the final fetch.

## Executed checks

| Directory | Command | Result |
| --- | --- | --- |
| backend | `uv run pyright src/` | 0 errors, 0 warnings |
| backend | `uv run python -c "from store_emulator.server.main import app; print('OK')"` | `OK` |
| backend | `uv run pytest --basetemp=/workspace/.verification/twinstore-collection-checks/pytest-data` | 3,303 passed, 1 skipped; 188.75 s |
| frontend | `npm exec --yes --package=pnpm@10.33.0 -- pnpm build` | Passed, including TypeScript; Vite 26.03 s |
| frontend | `npm exec --yes --package=pnpm@10.33.0 -- pnpm lint` | 0 errors, 19 existing warnings; none in changed files |
| frontend | `npm exec --yes --package=pnpm@10.33.0 -- pnpm test` | 302 passed across 54 files; 43.59 s |
| repository | `git diff --cached --check` | Passed |

The first frontend build caught an optional array-element spread in a new test fixture; explicit fixture fields
fixed it before the successful full build and test run. The existing opt-in Grounding DINO test is skipped because
it requires the capture extra and `PARASTORE_TEST_GDINO=1` (approximately 700 MB model download). Build warnings
concern large chunks and Babel-plugin timing. Frontend build, lint and tests ran sequentially. The workspace
`--basetemp` changes fixture storage only. Raw logs remain local under
`/workspace/.verification/twinstore-collection-checks/`.

## Regression coverage

- Untouched plans have unrecorded tail capacity, not known missing customers. Empty denominators remain unknown.
- Enrolled purchase/delivery unknowns, enrollment gaps and unused slots before later enrollment produce distinct
  actions. Both missing fields share one assignment; a known refusal alone does not become a correction task.
- Staff/shift and assigned-arm denominators remain separate. Assignment storage order does not change the report.
- Flipping every known purchase value leaves the complete JSON report and checklist CSV unchanged.
- Readiness agrees with existing closure rules; below-target closure retains sequence-review flags. CSV has one
  row per issue and revision metadata, or headers only when no issues exist.
- Read-only API requests preserve the saved pilot. Reviewed imports update checks; closure and source-report
  deletion preserve access. Older pilots need no migration, and missing scopes return errors.
- UI opens collection checks without requesting the full purchase-results endpoint. Filters, pagination, unknown
  rates, errors, corrected revisions, locked closure and checklist invalidation after imports are covered.
- Existing fixed-sample, missing-outcome, assigned-arm, import-review and locked-closure tests remain passing.

## Limits

No live model, actual store dataset or physical store workflow was used. This module makes no model calls and
checks submitted records rather than independently verifying purchases or script delivery. The default view
separates collection monitoring from purchase results; it does not enforce blinding or prevent repeated testing.
Recording gaps are prompts to review source records, not evidence of skipped customers or staff misconduct.
There are no encounter timestamps for overdue checks. No outcomes are imputed and no enrollment, sample-size,
stopping or closure rules are changed. Staff/shift comparisons do not correct confounding or clustering. The
follow-up CSV is not an importable observation sheet; verified corrections use the existing reviewed import.
