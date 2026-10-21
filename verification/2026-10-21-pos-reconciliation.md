# Field POS reconciliation — verification

Verified on 2026-10-21 on `feat/operator-modules`, preserving all operator modules through `6964866` and the
staff-script screening from `f3c7905`. Integrated fetched heads: `feat/vision-lab` at `7b5b839`,
`feat/store-scenarios` at `082210a`, `feat/parastore-v3` at `2e13bd3` and `fix/edge-case-loop-20261021` at
`0e147b8`. All are ancestors of the tested tree. The store-scenarios merge had one conflict in the wording of
the no-display-space error; the existing wording and both branches' functional changes were preserved.

## Executed checks

| Directory | Command | Result |
| --- | --- | --- |
| backend | `uv run pyright src/` | 0 errors, 0 warnings |
| backend | `uv run python -c "from store_emulator.server.main import app; print('OK')"` | `OK` |
| backend | `uv run pytest --basetemp=/workspace/.verification/twinstore-pos-reconciliation/pytest-data` | 3,804 passed, 1 skipped; 208.68 s |
| frontend | `npm exec --yes --package=pnpm@10.33.0 -- pnpm build` | Passed, including TypeScript; Vite 20.89 s |
| frontend | `npm exec --yes --package=pnpm@10.33.0 -- pnpm lint` | 0 errors, 19 existing warnings; none in changed files |
| frontend | `npm exec --yes --package=pnpm@10.33.0 -- pnpm test` | 349 passed across 60 files; 43.36 s |
| repository | `git diff --cached --check` | Passed |

The targeted engine/API run passed 39 tests in 4.52 s; the targeted UI run passed 20 tests in 4.69 s. An initial
targeted API run failed in fixture setup because the custom temporary directory's parent had not been created;
creating the verification directory resolved it. No application change was needed. Frontend build warnings
concern large chunks and Babel-plugin timing; build, lint and tests ran sequentially. Raw logs remain local under
`/workspace/.verification/twinstore-pos-reconciliation/`. The workspace `--basetemp` changes fixture storage only.
The skipped test is the existing opt-in Grounding DINO test, which requires the capture extra and
`PARASTORE_TEST_GDINO=1` to download its model. Existing fixed-sample, import-history, closure and collection-check
regressions passed with the new reconciliation tests and all integrated upstream tests.

## Regression coverage

- Exact SKU matching preserves leading zeros and case. Only unknown purchases of already enrolled encounters
  receive positive proposals; refusal, unknown delivery, enrollment, known outcomes and other assignments are kept.
- Positive evidence conflicting with a recorded no, unknown assignments and unlinked transactions are surfaced
  without changing observations. No target sale or zero net units never creates a negative outcome.
- Multiple receipts for one assignment produce one conversion proposal, source order does not affect proposals,
  and separate staff/shift assignments remain separate. Replaying an applied file proposes no duplicate purchase.
- Duplicate transaction/SKU lines and cross-assignment transaction reuse within a file reject the preview.
  Invalid quantities, pilot IDs, tokens, schema, encoding, malformed CSV and size/row limits are covered.
- Preview leaves pilot bytes and stored files unchanged. Proposals pass through the existing full-sheet review,
  import history and revision checks. Closed/stale pilots reject reconciliation; invalid requests preserve data.
- UI tests cover filtering/pagination, verification before handoff, the second full-sheet review before saving,
  the source hash in the editable reason, unchanged filter scope, zero-proposal blocking, overlapping requests,
  oversized files, errors and stale candidate rejection without writing.

## Limits

No real store data, live POS system or model was used. This module makes no model calls. Assignment links,
finalized sale status, net returns and the outcome window must be verified in the source system. Partial coverage
does not identify nonbuyers. Raw POS data and match reports are not retained; no transaction registry exists to
detect reuse across separate files or pilots. The source hash is an identifier, not proof or authentication. The
normal reviewed import retains changes and the submitted reason, not independently verified purchase evidence.
Matching does not fix repeated shoppers, missing outcomes, staff/shift confounding or repeated testing; fixed
sample and closure rules remain unchanged. A retained anonymous transaction registry with explicit correction
semantics is a candidate for a later cycle.
