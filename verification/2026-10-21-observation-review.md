# Field observation import review — verification

Verified on 2026-10-21 on `feat/operator-modules`, retaining the prior operator modules through `e4a7bfc`.
Integrated development heads: `feat/vision-lab` at `9083db3`, `feat/store-scenarios` at `aa6381d`,
`feat/parastore-v3` at `6a3d549`, and `fix/edge-case-loop-20261021` at `e52903e`.

## Executed checks

| Directory | Command | Result |
| --- | --- | --- |
| backend | `uv run pyright src/` | 0 errors, 0 warnings |
| backend | `uv run python -c "from store_emulator.server.main import app; print('OK')"` | `OK` |
| backend | `uv run pytest --basetemp=/workspace/.verification/twinstore-observation-review/pytest-data` | 2,637 passed, 1 skipped; 195.92 s |
| frontend | `npm exec --yes --package=pnpm@10.33.0 -- pnpm build` | Passed, including TypeScript; Vite 24.76 s |
| frontend | `npm exec --yes --package=pnpm@10.33.0 -- pnpm lint` | 0 errors, 19 existing warnings; none in changed files |
| frontend | `npm exec --yes --package=pnpm@10.33.0 -- pnpm test` | 258 passed across 48 files; 39.26 s |
| repository | `git diff --cached --check` | Passed |

The skipped test is the existing opt-in Grounding DINO test. Build emitted chunk-size and Babel-plugin timing
warnings. Frontend tests ran after the build to avoid the resource contention observed in the previous cycle.
The workspace `--basetemp` changes fixture storage only. Logs are retained locally under
`/workspace/.verification/twinstore-observation-review/`.

## Regression coverage

- Exact diffs distinguish unknown, false and true values; enrollment removals and purchase reversals are counted
  separately. Review tokens change with the file, saved values, pilot or revision. Preview leaves data untouched.
- The API requires a review token and reason. Invalid sheets, swapped files, stale reviews and overlapping writes
  preserve existing records. A semantic no-op leaves the revision and import history unchanged.
- A simulated failure after writing import details but before the atomic pilot replacement does not publish a
  history entry or change observations. A retry succeeds without duplicate history. Only referenced imports are read.
- Historical before/after values survive closure. Missing committed details fail the export instead of silently
  omitting records. Legacy pilots disclose the history boundary. CSV reasons that resemble formulas are escaped.
- UI tests cover preview without saving, reasons and confirmation, cache updates after application, discard,
  no-op sheets, failed/stale requests, closing while a preview is pending, and history/export after closure.
- Existing missing-outcome, fixed-sample, assigned-arm and locked-closure tests remain passing.

## Limits and API change

The import API now requires the preview token and reason; see `USAGE.md` for the multipart workflow.
No live model or real-store dataset was used, and no model calls are part of this feature. These are submitted
observation changes, not independently verified purchases. Reasons do not authenticate a reviewer; the content
hash is not a signature or tamper-proof ledger. Changes made before the recorded history boundary cannot be
reconstructed. Keep the pilot JSON and referenced import-detail files together in backups. Review and history
do not correct optional stopping, repeated-test selection, missing outcomes or staff/shift confounding.
