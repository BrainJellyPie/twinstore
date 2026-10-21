# Staff-script cost scenarios — verification

Verified on 2026-10-21 on `feat/operator-modules`, preserving operator results through `ccfbee7` and
staff-script screening from `f3c7905`. Integrated fetched heads: `feat/vision-lab` at `8aeddc1` and
`feat/parastore-v3` at `1d5fecf`. The fetched `feat/store-scenarios` at `b7a99c5` and
`fix/edge-case-loop-20261021` at `ef2e015` were already included. Integration commits are `1e202ca` and
`f96d700`. The README and changelog had documentation conflicts: retained the incoming reorganized README,
moved the existing sensitivity description into its new Field pilots section, and retained both the
sensitivity changelog entry and the updated seven-tab Market description. No functional code conflicts,
discarded operator modules or forced updates.

## Executed checks

| Directory | Command | Result |
| --- | --- | --- |
| backend | `uv run pyright src/` | 0 errors, 0 warnings |
| backend | `uv run python -c "from store_emulator.server.main import app; print('OK')"` | `OK` |
| backend | `uv run pytest --basetemp=/workspace/.verification/twinstore-field-economics/pytest-data` | 5,449 passed, 1 skipped; 256.59 s |
| frontend | `npm exec --yes --package=pnpm@10.33.0 -- pnpm build` | Passed, including TypeScript; Vite 28.73 s |
| frontend | `npm exec --yes --package=pnpm@10.33.0 -- pnpm lint` | 0 errors, 19 existing warnings; none in changed files |
| frontend | `npm exec --yes --package=pnpm@10.33.0 -- pnpm test` | 479 passed across 71 files; 57.26 s |
| repository | `git diff --cached --check` | Passed |

Targeted engine/API checks passed 43 tests in 5.33 s; targeted UI checks passed 27 tests across three
files in 5.32 s. Dependencies were installed using `uv sync --locked` and pnpm 10.33.0
`install --frozen-lockfile`. Frontend build, lint and tests ran sequentially. Existing build warnings concern
large chunks and Babel-plugin timing. The skipped backend test is the existing opt-in Grounding DINO test,
which requires the capture extra and `PARASTORE_TEST_GDINO=1` (approximately 700 MB model download).
The workspace basetemp only relocates test fixtures. Raw logs remain local under
`/workspace/.verification/twinstore-field-economics/`.

## Regression coverage

- Applies the same linear cost transformation to the completed fixed plan's conversion estimate and original
  conservative interval. Planned-count weighting is preserved by complete balanced arm counts. Exact rational
  arithmetic avoids a spurious nonzero point estimate at break-even before JSON number conversion.
- Covers cheaper B, fractional minor units, thresholds outside the feasible conversion-difference range,
  zero contribution, zero labor cost, zero daily traffic and maximum bounded inputs. At zero contribution
  the threshold is undefined; no arbitrary zero threshold is substituted.
- All-zero and all-one purchase records retain the original conversion uncertainty. Complementing outcomes
  and swapping staff times reverses the contribution scenario. Refusal/non-delivery stays in the assigned
  arm; changing delivery alone or product selling price does not alter entered costs or results.
- Strict bounded integers reject negative, fractional, boolean, string-coerced, infinite and excessive inputs.
  Open pilots, unused slots, unknown outcomes, mismatched assignments, stale revisions and currency changes
  are rejected without selecting complete-case subsets or imputing observations.
- API tests cover creation, reviewed import, closure, preview and CSV export, including preservation of all
  saved pilot/history bytes, deletion of the source synthetic screening job, missing resources and corrupt
  saved observations. No scenario files or new pilot fields are written.
- CSV contains source revision, currency, assumptions, output units and conditional interpretation, retains
  fractional values and an empty undefined threshold, and escapes spreadsheet formula prefixes.
- UI tests use the fetch helper and verify eligibility gating, initially blank assumptions, explicit zeros,
  valid request bodies, input limits, pending-state controls, server errors, result/export invalidation after
  edits, exact snapshot export, successful browser download/URL cleanup and export error reporting.
- Existing staff-script, field-pilot, sensitivity, collection, import/history, POS, receipt, movement,
  restocking and PDF regressions pass alongside the integrated upstream suite.

## Limits and next candidate

No real store records, measured service times, live POS system or live model were used. Fixtures are synthetic
test data only. This module makes no model calls. Operators must supply a common net target-product contribution
per converted encounter, loaded hourly labor cost, average whole staff seconds per assigned encounter in each
arm, and eligible daily volume. Costs are not inferred from selling price, unit margin or virtual shoppers.

The conditional range holds all those assumptions fixed. It excludes their uncertainty, other basket effects,
fixed implementation costs, capacity changes and future demand. Daily scaling is not a prediction interval for
realized profit. Editing assumptions adds no evidence and does not justify repeated tests or selecting favorable
results. Complete closure does not verify the collection protocol or fix clustering, repeated shoppers,
confounding or a changed offer. The original full-plan result remains primary. Scenarios are not persisted;
retain the CSV for review. Anonymous response-time CSV linkage with explicit missingness and source tracking
would be a useful next step toward replacing manual time assumptions with verified observations.
