# Observed staff time: migration, boundary review and verification

## Repository migration

- User switched development to `BrainJellyPie/twinstore`; old `/workspace/parastore` was clean and preserved.
- Cloned new `main` at `0b45b5ed94d1213d2db0e4d830dcfbe01a2b4dfd`. Inspected AGENTS and actual source.
  The new repository has rewritten history; comparing tip contents identified only two missing operator modules.
- Ported old sensitivity `ccfbee72` as `2b617f10`, and cost scenarios `b285abda` as `1cb6b2ac` onto
  `feat/operator-modules`. README/CHANGELOG conflicts were resolved to keep the new seven-tab description,
  current in-repository figures and both feature descriptions. No old duplicate history was merged.
- Integrated new `origin/main` / edge-case branch `f17da590` (net POS returns) and
  `origin/feat/store-scenarios` `02abf8ed` (mobile playback/run controls) before full checks.
- Existing recurring task now targets the new repository, preserves its schedule, requires broad user-needs
  research and explicitly includes a post-implementation boundary-testing / bug-fix phase. No duplicate task.

## Feature and evidence

Read [candidate research](2026-10-21-feature-candidates.md) for sources, different user groups, implementation
selection timing and the next-domain candidates. These are documented product hypotheses, not interviews.

- English UI under a completed field pilot, typed API and pure engine calculation for anonymous observed
  staff-time CSVs. Template and audit export, exact assignment matching, immutable source revision and SHA-256.
- Unknown times remain unknown, including absent rows. Means and differences require all planned encounters;
  refusals and non-delivery stay in assigned arms. Complete means respect planned-count block weights.
- No calls to models, no new significance tests, no manufactured human observations or inferred sales effects.
- Timing review does not save or mutate pilot observations; audit/source files must be retained by the operator.

## Separate boundary phase

Basic checks passed first: backend **22 passed** (engine + field pilot API); UI **3 passed**; pyright zero errors.
Then added targeted boundary/regression coverage:

- Blank versus explicit zero, completely blank template, omitted rows, one complete arm / one missing arm.
- Duplicate blank assignment, foreign assignment, wrong pilot, exact fixed-plan identity, changed arm/staff/shift,
  deleted/duplicated slots, open pilot, unused slots and incomplete delivery/purchase records.
- 0, 0.001 and 3600 seconds; excessive values, negative/signed zero, infinities, NaN, exponents, whitespace,
  Unicode numerals, control characters, excess decimal precision; valid leading zeros and quoted fields.
- UTF-8 BOM, reordered headers, duplicate/extra headers, bad UTF-8, malformed quotes, empty rows and empty files.
- Full **10,000-assignment** case and 10,001-row rejection, 2 MB client boundary and oversized server rejection.
- Unequal block sizes, source row-order independence, exact small signed differences, refusal/purchase invariance,
  CSV unknown/zero distinctions, formula escaping and retained source hash/revision.
- API stale revision, missing pilot, wrong saved pilot identity, invalid revision, export errors and byte-for-byte
  preservation of saved pilot state. UI disabled pending controls, cancelled/replaced files, late response after
  revision change, server/network failures, exact export source and blob URL cleanup.

Actual failures reproduced before fixes:

1. Tiny time differences were rounded to `-0` by a fixed three-decimal UI formatter. The boundary UI run had
   **1 failed / 8 passed**. Fixed with eight significant digits; `-0.00005` now survives display.
2. Zero daily traffic multiplied negative scenario values into `-0.0`, exported as apparent negative zero.
   The boundary backend run had **1 failed / 93 passed**. Fixed exact zero daily values and zero-cost range
   normalization. Added the corresponding zero-margin/equal-time regression as well.

After fixes: focused backend **95 passed (7.01 s)**; focused UI **9 passed (2.54 s)**.

## Full required checks

At the migrated feature snapshot including upstream `f17da590` / `02abf8ed`:

| Check | Actual result |
| --- | --- |
| `uv run pyright src/` | 0 errors, 0 warnings |
| `uv run python -c "from store_emulator.server.main import app; print('OK')"` | OK |
| `uv run pytest --basetemp=/workspace/.verification/twinstore-timing/pytest-full` | 5,809 passed, 1 skipped; 284.48 s |
| pnpm 10.33.0 `build` | Passed TypeScript + Vite; Vite 28.56 s |
| pnpm 10.33.0 `lint` | 0 errors, 19 pre-existing warnings; no warnings in changed files |
| pnpm 10.33.0 `test` | 508 passed, 73 files; 64.45 s |
| `git diff --check` | Passed |

Dependencies installed with `uv sync --locked` and pinned `pnpm install --frozen-lockfile`.
Frontend commands used `npm exec --yes --package=pnpm@10.33.0 -- pnpm <command>`.
Existing Vite large-chunk/plugin-timing notices remain. The optional GroundingDINO model test is skipped;
its extra dependencies and approximately 700 MB model download are not part of this offline check.
Local execution logs: `/workspace/.verification/twinstore-timing/`, including the failing boundary runs
and successful repeats. An early frontend test-file creation used the wrong working-directory prefix and
was corrected before the basic test; root-directory `uv` invocations were likewise corrected and are not
counted as verification passes.

## Final upstream integration and repeat verification

While the first full suite was running, new upstream commits arrived. After it passed, committed the feature
as `c70fe22a`, then merged `origin/main` at `7196f5c1` into `55ab81f3`. This also includes `b7a4ac5a`'s
conjoint profile uniqueness fix and 216 additional regression cases. The other upstream changes clean up
study-specific references in comments/changelog and one settings paragraph. No feature conflicts or lost
local changes occurred. All inspected main, edge-case and store-scenario heads are ancestors of this snapshot.

Repeated every required check on the final integrated code at `55ab81f3`:

| Check | Actual final result |
| --- | --- |
| Backend strict pyright | 0 errors, 0 warnings |
| App import boot | OK |
| Backend full pytest | **6,025 passed, 1 skipped; 269.01 s** |
| pnpm 10.33.0 build | Passed TypeScript + Vite; Vite 24.80 s |
| pnpm 10.33.0 lint | **0 errors, 19 existing warnings**; no warning paths intersect changes |
| pnpm 10.33.0 test | **508 passed, 73 files; 61.26 s** |
| Diff whitespace check | Passed |

Final logs use the `integrated-*.log` prefix in the same local verification directory. The only subsequent
change is this verification record. `/workspace/parastore` remains clean and synchronized with its old
remote; `twinstore`'s origin is `https://github.com/BrainJellyPie/twinstore.git`. The existing recurring task
was read back and confirmed enabled with the new repository, broad candidate research and boundary-fix phase.

## Limits

All added test measurements are explicit offline fixtures. No live store, operator interviews, real POS/timing
file or live LLM/VLM was used. Uploaded measurements and timing protocol adherence cannot be independently
verified. The module does not correct measurement error, confounding, clustering or selective time collection.
Means are descriptive; cost assumptions remain separately chosen whole seconds. This is not a payroll,
capacity, staff-performance or realized-profit system. Boundary coverage is substantial, not exhaustive.
