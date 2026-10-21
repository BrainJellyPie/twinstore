# Paired price × sign review: verification record

## Repository and selection

- Used `/workspace/twinstore`, origin `https://github.com/BrainJellyPie/twinstore.git`, branch
  `feat/operator-modules`, initially clean at `2f6d49f4`. Preserved the old parastore directory.
- Inspected actual commits and source, then integrated main `2a794c5f`, scenarios `01c9a16f` and edge-case
  `88158ef5` into baseline `6e723303`. Existing inventory and staff/operator modules remain intact.
- Read root AGENTS, including the current localization scope; this new module uses English UI/API text.
  No nested AGENTS files were found. Managed runtime reported current, connected readiness and an enforced
  unrestricted HTTP policy; credentials were not inspected or printed.
- [Candidate review](2026-10-21-factorial-candidates.md) records public sources actually fetched, unsuccessful
  source requests, three different user/problem areas, required data and the pre-implementation metric contract.
  Selection followed the prior inventory cycle, avoiding another staff-script or inventory subfeature.
- Feature commit: `2d1382fe`. Before full verification, integrated newer main `67afbcd7` and scenarios
  `60c149c3` as snapshot `b33b5c5c`, including photo assets `94623e0b` and edge fixes `60717a09`. All fetched
  development heads were ancestors. Merges were conflict-free; no force push or overwrite of other work.

## Implementation and interpretation

New A/B runs retain minimal scalar outcomes and sampled IDs before the existing all-arm intersection.
The completed experiment report connects a new component, query/mutation services, typed HTTP API,
application source validation, domain schemas and pure engine arithmetic. It uses the existing runner;
there are no additional simulation/model calls. Older aggregate-only experiments remain unavailable.

The selected cells must represent one price/discount change, one promotion-sign change on the same SKU,
and exactly their combination. Four effective store hashes must differ, and application warnings block
analysis. One selected whole-basket metric produces two averaged main effects and a difference-in-differences
interaction. All four means and contrasts use one complete cohort. Missing observations are not zero.

Fixed-seed, bounded-batch paired bootstrap intervals require all actually sampled shoppers in every selected
cell and at least 30 complete shoppers. Percentile tails apply a three-contrast Bonferroni adjustment; the
reported family coverage is nominal/approximate under bootstrap assumptions. No repeated-analysis protection,
real-sales effect, p-value, winner, annualization or daily-traffic multiplication is claimed. CSV exports
source hash, exact selections/changes, metadata, formulae and all selected cells, including incomplete rows.

## Basic stage, then separate boundary stage

Basic engine/API: **3 passed in 3.31 s**; UI: **3 passed in 2.25 s**; strict pyright: **0 errors, 0 warnings**.
An initial API test fixture incorrectly referenced `Persona.arrival_time`; corrected it to build the fixture's
time from `arrival_hour`. That was a test setup error, not a product defect or a successful verification run.

Boundary coverage then included:

- Hand-calculated effects and difference-in-differences; large between-shopper baselines cancel through
  pairing instead of creating independent-cell uncertainty. Negative effects and exact zero survive export.
- One shopper, 29/30 interval threshold, all-zero spend, free purchases, binary purchase and unit outcomes.
- One/two missing cells, a shopper absent in every arm, empty four-way intersection, explicit excluded rows
  and no zero imputation. API regression confirms raw capture occurs before the original common-cohort filter.
- Invalid types, booleans masquerading as counts, fractional counts, negatives, NaN/infinity and values beyond
  spend/unit limits. Duplicate/foreign shopper IDs, empty/oversized panels and wrong arm order rejected.
- No-op layouts, unapplied changes, other SKUs, extra manipulations, incorrect factor kinds, unknown/repeated
  selections and malformed hashes. Reversed ordering of the same two commuting changes is supported.
- Unicode/comma/formula-prefix arm labels; formula text escaped while numeric negative effects stay numbers.
  Row-order invariance and the complete **3,000-shopper** case with 4,000 resamples; 3,001 sampled IDs rejected.
- API mismatched experiment identity, malformed/oversized (8 MB) snapshots, legacy/missing artifacts, incomplete
  jobs, deleted projects/experiments, changed-source export rejection and independent concurrent metric reviews.
  Read-only operations leave saved files byte-for-byte unchanged. Unsupported capture preserves ordinary A/B completion.
- UI on-demand source loading, unavailable legacy sources, missing estimates versus zero, tiny signed values,
  input locking while pending, network/source-load failure recovery, outcome edits clearing results/export,
  stale-source reloads, late preview after experiment change, exact export request, URL cleanup and no delayed
  download after the experiment component unmounts.

**Actual defect reproduced:** a saved outcome could say no purchase while units/spend were positive, or say
purchase with zero units. These contradictory records were previously accepted. The focused regression run
had **5 failed / 46 passed**. Added a domain consistency check: purchase iff units are positive, and a
nonpurchase must have zero spend. Zero spend with positive units remains a valid free purchase. The API now
rejects an inconsistent stored snapshot, and optional invalid capture does not turn the original A/B run into
a failure. This is defensive data-integrity validation, not a claim that a live store produced such records.

After the fix: related backend tests **64 passed in 5.42 s**, including existing common-panel regressions;
UI boundary tests **11 passed in 2.50 s**; strict pyright **0 errors, 0 warnings**.

## Full required verification

Commands run on integrated snapshot `b33b5c5c`; execution logs reside at
`/workspace/.verification/twinstore-factorial/`. Frontend uses repository-pinned pnpm 10.33.0 via
`npm exec --yes --package=pnpm@10.33.0 -- pnpm <command>`. Backend pytest's workspace basetemp supports
the existing project-relative fixtures. All checks below actually completed on the integrated code; only
this verification document changed afterward.

| Check | Actual result |
| --- | --- |
| `uv run pyright src/` | 0 errors, 0 warnings |
| `uv run python -c "from store_emulator.server.main import app; print('OK')"` | OK |
| `uv run pytest --basetemp=/workspace/.verification/twinstore-factorial/pytest-full` | **8,155 passed, 1 skipped; 322.36 s** |
| pnpm 10.33.0 `build` | TypeScript + Vite passed; Vite 27.44 s |
| pnpm 10.33.0 `lint` | **0 errors, 19 pre-existing warnings**; warning paths do not intersect feature files |
| pnpm 10.33.0 `test` | **1,135 passed, 95 files; 98.22 s** |
| `git diff --check` / staged whitespace check | Passed |

The optional GroundingDINO integration remains skipped without its capture dependencies, explicit opt-in
and large model download. Existing Vite large-chunk and plugin-timing notices remain. No live model validation
is inferred from these offline tests. `basic-`, `boundary-` and `full-` logs distinguish stages and actual failures.

Before push, re-fetched `origin/feat/operator-modules` and confirmed its `2f6d49f4` head is an ancestor of
this work. The development heads used for validation are explicit above; subsequent arrivals can be assessed
in the next cycle. The old parastore working directory remains clean. Read back the existing automation:
enabled, hourly, targeting twinstore, with multi-domain source research and the separate boundary/fix stage.

## Limitations and next candidates

All added numeric tests use explicit offline fixtures, with a stub evaluator through the real A/B application
and API path. No live VLM/LLM, real-store marketing outcomes, operator interviews or market-demand study was
used. The ordinary full test suite supplies additional existing offline regressions. Browser rendering is
tested with jsdom; no cross-browser usability study was performed.

This module supports only same-SKU price/discount × sign designs and whole-basket outcomes. Requested model
selection is retained; an app-default model is not pinned to a provider revision. Source hashes detect change,
not authenticity. Percentile intervals and a minimum panel guard cannot fix model bias, correlated personas,
selection after results, repeated exploratory analyses or differences between synthetic and real consumers.
Reviews are read-only and selections are not persisted; retain exports. General factorial designs, prospective
protocol registration and live-human experiments are outside this module. Coverage is broad, not exhaustive.

Next different-domain candidates: competitor unit-price normalization for operators, or prospective protocol
snapshots/amendment comparisons for researchers. Recheck existing modules and current development before choosing.
