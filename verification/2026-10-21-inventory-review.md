# Inventory performance review: integration, boundary review and verification

## Repository and selection

- Worked in `/workspace/twinstore`, origin `https://github.com/BrainJellyPie/twinstore.git`, on
  `feat/operator-modules`; started clean at operator head `b2a07b2b`. Old `/workspace/parastore` was preserved
  and its status remained clean. No force push, reset or removal of another worker's changes.
- Compared actual remote history and source. Merged main `65022a78` and store scenarios `664b3328` as
  `2d13cd43` / `ead73865`, preserving the previously implemented operator modules.
- After focused boundary verification, recorded the new module as `f010cf7d`. Fetched again and merged main
  `5407cb68` as `3b9e237f`. This includes scenario `4e0b4c62`, edge-case `bb29071f` and photographic shopper
  `fe9aca99`. All inspected development heads were ancestors of the integrated snapshot; no merge conflicts.
  Read the updated AGENTS language policy. New inventory UI/API text remains English as requested.
- Before coding, compared inventory review, research protocol amendments and factorial interaction design;
  see [candidate research and sources](2026-10-21-inventory-candidates.md). Recent work focused on staff
  scripts, so this cycle chose a distinct operational workflow. Public-source requirements hypotheses are
  not interviews, validated demand or evidence of financial benefit.

## Connected feature

**Market → Inventory** accepts an explicitly scoped period/currency and observed SKU CSV. Domain models,
pure engine calculations, project-scoped application validation, multipart API, mutation services and the UI
are connected. A header-only template and audit export complete the workflow.

- Exact decimal quantity reconciliation; net sell-through uses a documented period denominator.
- Supplied net sales/COGS and opening/closing inventory values at cost produce gross profit, period turnover
  and GMROI. Negative profit is retained; invalid denominators and negative COGS receive explicit treatment.
- Inconsistent stock/value records withhold ratios while keeping all supplied rows in financial totals.
  Portfolio ratios divide summed money by summed average cost, never average SKU ratios.
- Exports retain source SHA-256, period, method, source values, results and reason flags. No stock mutation,
  inferred demand, simulation, model calls, annualization, hypothesis tests or promotion-effect claims.

## Basic verification, then separate boundary phase

Basic engine/API checks passed first: **4 passed in 4.90 s**; UI **3 passed in 3.47 s**; strict pyright
**0 errors, 0 warnings**. Then expanded coverage around observable failure modes, including:

- Empty and header-only files, blank cells versus explicit zero, absent/duplicate/extra columns, short rows,
  blank rows, malformed quoting, non-UTF-8 files, UTF-8 BOM and reordered columns.
- Exact duplicate SKU rejection; valid Unicode, commas and emoji; outer whitespace, controls, zero-width
  characters and overlong identifiers rejected. Spreadsheet formula-prefix text escaped in export while
  negative numeric inputs remain numbers.
- Zero supply/cost, negative expected stock, stock mismatch, zero stock with nonzero cost, customer returns
  larger than sales, negative COGS/profit and unavailable ratios. No NaN/Infinity JSON or fabricated zeros.
- Negative quantities, signed/scientific numbers, NaN/Infinity, Unicode digits, thousands separators,
  excess decimals and out-of-bound money/quantities rejected before producing any partial result.
- Fractional quantities such as 0.1 + 0.2 reconcile exactly; a 0.001 mismatch is retained. Half-minor-unit
  average cost is supported. Unequal SKU costs use portfolio weighting rather than averaging ratios.
- One inclusive day, leap day, 3660-day maximum, invalid dates and reversed/overlong periods.
- Full **2,000-SKU** maximum-value input preserves totals (including 4 quadrillion minor-unit gross profit
  within JavaScript's safe integer range); 2,001 rows rejected. Client file boundary at 2 MB, oversized file
  rejection at client/server, row-order invariance and retained input-source hash.
- API preview/export agreement, invalid upload/period responses, deleted projects and concurrent independent
  reviews. Byte comparisons show no changes to saved project data during successful or invalid reviews.
- UI blank scope, pending-input locking, file cancellation/replacement, scope edits invalidating results and
  export, late response after project change, network errors, failed export after deletion, exact export
  request/filename and temporary blob URL cleanup.

**Actual boundary bug reproduced:** return-heavy periods correctly withheld portfolio turnover when net
COGS was negative, but its reason was missing from the portfolio CSV row and the summary UI. The first
boundary runs had **1 failed / 51 passed** in the backend and **1 failed / 8 passed** in the UI. Added a
`negative_cogs` portfolio export flag and an explicit summary explanation. Regression tests now pass:
focused backend **52 passed in 4.51 s**; UI **9 passed in 2.93 s**. This was a reporting gap, not a changed
inventory formula.

The worksheet is read-only, with no saved mutable review revision. Stale-source risk is addressed by retaining
the uploaded file/period for export, clearing results on edits and separating keyed project views; there is no
revision overwrite to test. Repeated hypothesis testing and staff/shift confounding do not apply to these
descriptive inventory ratios. No inference about promotion performance is made.

## Full required checks

Full integrated checks were executed; local logs are under
`/workspace/.verification/twinstore-inventory/`. Frontend uses repository-pinned pnpm **10.33.0** through
`npm exec --yes --package=pnpm@10.33.0 -- pnpm <command>`. Backend pytest uses a workspace `--basetemp`
because existing tests create project-relative fixtures after changing directories.

The first complete pass on `3b9e237f` had **6,807 backend tests passed, 1 skipped (277.50 s)** and
**774 frontend tests passed, 82 files (72.12 s)**. Strict pyright had 0 errors/warnings, app import printed
`OK`, build passed (Vite 26.62 s), and lint had 0 errors / 19 existing warnings.

The pre-push remote check then found store-scenario `b2a817e0` (2/4/6-seat layouts and accurate capacity).
Merged it without conflicts as `c6a0be48` and repeated all required checks on that final integrated code.
The other fetched development heads and operator head were unchanged. New inventory files were untouched
by this merge. The existing hourly automation was also read back: enabled, targeting `BrainJellyPie/twinstore`,
with broad candidate research and the separate boundary-test/fix phase retained.

Final results on `c6a0be48` (only this verification document changed afterward):

| Required check | Actual result |
| --- | --- |
| `uv run pyright src/` | 0 errors, 0 warnings |
| `uv run python -c "from store_emulator.server.main import app; print('OK')"` | OK |
| `uv run pytest --basetemp=/workspace/.verification/twinstore-inventory/pytest-integrated` | **7,138 passed, 1 skipped; 268.94 s** |
| pnpm 10.33.0 `build` | TypeScript + Vite passed; Vite 19.70 s |
| pnpm 10.33.0 `lint` | **0 errors, 19 existing warnings**; none in the new inventory module files |
| pnpm 10.33.0 `test` | **797 passed, 84 files; 73.09 s** |
| `git diff --check` | Passed |

Final logs use the `integrated-` prefix; initial full checks use `full-`, and failing/passing targeted
boundary logs use `boundary-`. The skipped GroundingDINO test requires the capture extra, explicit
`PARASTORE_TEST_GDINO=1` and an approximately 700 MB model download. Existing Vite large-chunk/plugin-timing
notices remain. No new inventory lint errors or warnings were introduced.

Re-fetched the destination branch before push and confirmed the remote operator head `b2a07b2b` is an ancestor
of the verified work; no concurrent operator commits were overwritten. Development heads used for this
verification are recorded above so the next cycle can assess later arrivals against an explicit snapshot.

## Limits and next candidates

All numeric test cases are offline fixtures, not observed business results. No real operator CSV, inventory
audit, user interview or live model was used. The implementation verifies syntax and arithmetic, not the
truth of records, tax treatment, currency scale or valuation policy. Endpoint averages may miss replenishment
peaks; endpoint balance does not prove every intraperiod transaction was captured. Prior-period returns need
separate interpretation. Reviews are not persisted, so keep both original input and audit export. Boundary
coverage is broad but not exhaustive; no cross-browser or real-store usability study was performed.

Next different-domain candidates are protocol snapshots/amendment comparisons for research reproducibility
and predeclared price × POP factorial interaction analysis. Check existing manifests and experiment reports
again before choosing, and continue to distinguish synthetic screening from real marketing effects.
