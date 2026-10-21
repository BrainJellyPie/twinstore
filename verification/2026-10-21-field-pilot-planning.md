# Field pilot sample planning — verification

Verified on 2026-10-21, Python 3.13.5 and pnpm 10.33.0, on `feat/operator-modules`.
Integration includes `feat/vision-lab` / `fix/edge-case-loop-20261021` at `110303a`,
`feat/store-scenarios` at `e947473`, and `feat/parastore-v3` at `df16fb2`.
The existing operator-module work, including the saved staff-script and observed-pilot workflows, is retained.

## Executed checks

| Directory | Command | Result |
| --- | --- | --- |
| backend | `uv run pyright src/` | 0 errors, 0 warnings |
| backend | `uv run python -c "from store_emulator.server.main import app; print('OK')"` | `OK` |
| backend | `uv run pytest --basetemp=/workspace/.verification/twinstore-pilot-planning/final-pytest-data` | 1,771 passed, 1 skipped; 172.36 s |
| frontend | `npm exec --yes --package=pnpm@10.33.0 -- pnpm build` | Passed, including TypeScript; Vite 32.54 s |
| frontend | `npm exec --yes --package=pnpm@10.33.0 -- pnpm lint` | 0 errors, 19 existing warnings; none in the changed files |
| frontend | `npm exec --yes --package=pnpm@10.33.0 -- pnpm test` | 226 passed across 42 files; 28.88 s |
| repository | `git diff --cached --check` | Passed |

Build emitted chunk-size and Babel-plugin timing warnings. An earlier frontend test run executed alongside
the build timed out in the existing 40-by-40 grid zoom test at 5 seconds (225 other tests passed). The same full
test command passed after the build finished; no timeout increase, exclusion, or grid-code change was made.
An earlier backend run before the last upstream integration passed 1,768 tests with one skip.
The workspace `--basetemp` changes fixture storage only and avoids the smaller `/tmp` mount.
Execution logs are retained locally under `/workspace/.verification/twinstore-pilot-planning/`.

## Regression evidence and limits

- Sample requirements meet the requested conservative power bound; the preceding even sample does not.
  Exact binomial enumeration independently checks that the bound stays below detection probability in both
  directions. Unequal block sizes, limits, monotonicity, invalid/nonfinite inputs and numerical saturation are covered.
- API tests cover side-effect-free preview, project validation, recomputation from actual saved counts,
  persistence through observation import and closure, agreement with the final interval width, and older pilots.
- UI tests cover percentage-point input, applying suggested counts, saved assumptions, capacity/time shortfalls,
  invalid input, stale/pending calculations, errors, and avoiding a rounded 100% certainty claim.
- Existing fixed-plan, incomplete-outcome, intention-to-treat and locked-closure regression tests also pass.

This feature uses no model calls, baseline conversion estimates or synthetic scores as observed purchases.
Verification uses offline fixtures, not live models or real store records. Power and collection-day figures are
conditional planning calculations; independence, complete observations, a fixed stopping rule and the operator's
traffic estimate remain assumptions. Unmodeled clustering, repeat-customer interference, multiple-test selection,
shift-calendar feasibility and real sales effects have not been validated.
