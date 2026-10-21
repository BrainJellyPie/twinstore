# Budgeted restocking quantities — verification

Verified on 2026-10-21 on `feat/operator-modules`, preserving operator modules through `21a1830` and
staff-script screening from `f3c7905`. Integrated fetched heads: `feat/vision-lab` and
`fix/edge-case-loop-20261021` at `79914b8`, `feat/parastore-v3` at `cb7f30b`, and
`feat/store-scenarios` at `183df46`. All are ancestors of the tested tree. Integration completed without
conflicts; the resulting merge is `94d8f86`. The existing restock-priority estimates remain separate from
the new operator-entered inventory quantities and purchasing budget.

## Executed checks

| Directory | Command | Result |
| --- | --- | --- |
| backend | `uv run pyright src/` | 0 errors, 0 warnings |
| backend | `uv run python -c "from store_emulator.server.main import app; print('OK')"` | `OK` |
| backend | `uv run pytest --basetemp=/workspace/.verification/twinstore-restock-order/pytest-data` | 4,521 passed, 1 skipped; 224.61 s |
| frontend | `npm exec --yes --package=pnpm@10.33.0 -- pnpm build` | Passed, including TypeScript; Vite 20.50 s |
| frontend | `npm exec --yes --package=pnpm@10.33.0 -- pnpm lint` | 0 errors, 19 existing warnings; none in changed files |
| frontend | `npm exec --yes --package=pnpm@10.33.0 -- pnpm test` | 408 passed across 64 files; 50.39 s |
| repository | `git diff --cached --check` | Passed |

The targeted backend engine/API run passed 23 tests in 3.82 s. The initial targeted frontend run passed
18 tests in 2.57 s, including the existing priority calculator; the subsequent successful-download test
was included in the full frontend run. Dependencies were installed from the existing lockfiles with
`uv sync --locked` and `pnpm install --frozen-lockfile` using pnpm 10.33.0. Frontend build, lint and tests
ran sequentially. Build warnings concern large chunks and Babel-plugin timing. The skipped backend test
is the existing opt-in Grounding DINO test requiring the capture extra and `PARASTORE_TEST_GDINO=1`
(approximately 700 MB model download). Raw logs remain local under
`/workspace/.verification/twinstore-restock-order/`. The workspace basetemp only relocates test fixtures.

## Regression coverage

- Verified stockroom units are used first. Supplier packs round up; partial fulfillment, surplus,
  supplier caps, explicit priority and deterministic SKU tie-breaking are checked. Multiple audit
  levels do not duplicate a SKU's quantity, and changing modeled revenue losses cannot change the plan.
- One delivery fee is reserved and charged only when a pack is ordered. Zero-cost packs, no-order
  plans and fees exceeding the budget are covered. One hundred seeded randomized plans check budget
  and quantity conservation without floating-point monetary arithmetic.
- Strict bounded integers reject booleans, fractions, negative values and coercion. Currency mismatches,
  duplicate SKU inputs and items outside the audit's identified missing SKUs are rejected.
- API preview and export read a completed saved audit without writing it or running a model. Missing,
  unfinished, mismatched and orphaned sources fail. CSV contains source identifiers, excluded items,
  all entered values and computed quantities, with spreadsheet formula prefixes escaped.
- UI coverage checks unknown versus explicit zero counts, deduplicated SKUs, exclusions, invalid input,
  exact API requests, pending-state controls, error recovery and invalidation of stale results after
  edits. Export uses the successful request snapshot and downloads/revokes the generated blob URL.
- Existing staff-script, field-pilot, receipt, movement, restock-priority and PDF regressions passed
  alongside the integrated upstream suite.

## Limits and next candidates

No real store inventory, supplier feed, live model or actual sales were used. The feature makes no model
call. The operator must verify quantities, costs, available stockroom inventory, taxes and supplier limits;
photo facings and simulated revenue are never converted into stock counts. This is a sequential priority
allocation, not profit optimization. It supports one supplier fee structure per worksheet. Plans are
unsaved apart from the CSV export and do not place orders or reserve stock. Reusing inventory in multiple
plans can double-allocate it. Storage capacity, expiry, lead times and delivered quantities are not modeled.
No sales recovery or field-experiment effect is claimed. Stock reservations across plans, supplier lead
times, or a retained anonymous transaction registry for field POS reconciliation are follow-up candidates.
