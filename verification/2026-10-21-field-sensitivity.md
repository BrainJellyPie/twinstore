# Staff and shift sensitivity — verification

Verified on 2026-10-21 on `feat/operator-modules`. Preserved all operator modules through `b3545dd`,
including staff-script screening from `f3c7905`. Fast-forwarded to `feat/vision-lab` at `7926c55`, which
also contains the fetched heads `feat/parastore-v3` at `f44022d`, `feat/store-scenarios` at `b7a99c5`, and
`fix/edge-case-loop-20261021` at `ef2e015`. Ancestry checks passed; no merge conflicts or discarded changes.

## Executed checks

| Directory | Command | Result |
| --- | --- | --- |
| backend | `uv run pyright src/` | 0 errors, 0 warnings |
| backend | `uv run python -c "from store_emulator.server.main import app; print('OK')"` | `OK` |
| backend | `uv run pytest --basetemp=/workspace/.verification/twinstore-field-sensitivity/pytest-data` | 5,422 passed, 1 skipped; 258.00 s |
| frontend | `npm exec --yes --package=pnpm@10.33.0 -- pnpm build` | Passed, including TypeScript; Vite 19.11 s |
| frontend | `npm exec --yes --package=pnpm@10.33.0 -- pnpm lint` | 0 errors, 19 existing warnings; none in changed files |
| frontend | `npm exec --yes --package=pnpm@10.33.0 -- pnpm test` | 473 passed across 70 files; 61.84 s |
| repository | `git diff --cached --check` | Passed |

The targeted engine/API run passed 30 tests in 4.86 s. The targeted UI run passed 27 tests across three
files in 4.82 s. Its initial two failures were test assertions: one selected a repeated numeric label as
a unique element, and the other checked a query's pending state before the asynchronous notification.
Both were corrected. The first full build then found two strict TypeScript errors in fixture array
spreads that could include undefined; typed mapping replaced those spreads. The final full checks above
include that repair, the query configuration under `services/queries`, and the final CSV unit metadata.

Dependencies were installed from the existing lockfiles using `uv sync --locked` and pnpm 10.33.0
`install --frozen-lockfile`. Frontend build, lint and tests ran sequentially. Existing build warnings
concern large chunks and Babel-plugin timing. The skipped backend test is the existing opt-in Grounding
DINO test requiring the capture extra and `PARASTORE_TEST_GDINO=1` (approximately 700 MB model download).
The workspace basetemp only relocates fixtures. Raw final logs remain local under
`/workspace/.verification/twinstore-field-sensitivity/`.

## Regression coverage

- Unequal block sizes use precommitted planned-count weights, renormalized after removal. Removing a staff
  alias includes all of its shifts; removing a shift ID includes all matching staff blocks. A concrete
  multi-block fixture verifies full-plan, deletion, range, influence and opposite-sign calculations.
- Refusals and non-delivery remain in their assigned arms. Changing delivery alone or reordering saved
  assignments cannot change the report. Forty seeded binary-outcome fixtures agree with direct balanced
  arm counts, and complementing all outcomes reverses estimates while preserving reversal flags.
- Exact zeros are not opposite signs. Removing the only group yields unavailable values, not zero.
  Fraction arithmetic determines sign before conversion to JSON numbers, avoiding floating-point
  cancellation as a source of spurious sign reversals.
- Open pilots, unused slots, unknown enrollment, purchase or delivery, missing/duplicate assignments,
  altered sequences, arms and staff aliases reject the whole diagnostic. No incomplete subset is selected.
- API checks cover the create/import/close workflow, revision-bound JSON and CSV reads, invalid parameters,
  missing resources, early closure, corrupted assignments and source-screening deletion. Saved pilot bytes
  remain unchanged. No new persisted fields, observation updates or model calls are required.
- CSV retains every scope, revision, target SKU, denominator, weight and estimate, labels differences as
  proportions and the analysis as descriptive, escapes formula-like identifiers, and leaves unavailable
  values blank. Existing observation import, history, closure and collection regressions pass.
- UI tests exercise the actual fetch helper and verify explicit loading only after eligibility and request,
  request identity and revision, percentage-point display, all-scope export links, unavailable estimates,
  pending controls, errors without a stale export and cache separation across pilot/revision changes.

## Limits and follow-up

No real store observations, live POS system or live model were used; fixtures are synthetic test data only.
The feature makes no model call and does not infer sales from virtual shoppers. It is a descriptive group
deletion diagnostic, not a new confidence interval, hypothesis test, staff performance ranking or causal
adjustment. The original full-plan result stays primary. Overlapping deletions are not independent
replications, and selecting favorable rows or repeatedly restarting pilots remains invalid.

Alias and shift IDs are matched exactly; their real-world correctness is not verified. Differences can
reflect noise, composition, heterogeneity or protocol problems. Stable signs do not correct clustering,
repeated shoppers, interference or unmeasured confounding. Closure and complete records do not establish
that the saved outcome window or collection protocol was followed. A retained anonymous transaction
registry to detect POS evidence reuse across files, with explicit correction semantics, remains a useful
next candidate.
