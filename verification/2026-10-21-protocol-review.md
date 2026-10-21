# Research protocol history — verification (2026-10-21)

## Scope

Project-scoped research plans and append-only application amendment workflow with English UI, typed API,
pure canonical hashing/field-difference calculation and atomic application storage. No model calls or outcomes
are involved. Original snapshots remain intact; declared data stage is explicit and cannot move backward.
Plans capture outcome/window, analysis unit, planned independent units, sampling, assignment, missingness,
stopping and analysis/multiplicity rules. This does not certify their adequacy or enforce them on runs.

Public-source candidate research is in [the selection record](2026-10-21-protocol-candidates.md). No interviews,
market validation or real-store dataset was used. Existing operator functionality remains preserved.

## Basic checks before the separate boundary stage

- Python strict type check: 0 errors, 0 warnings.
- New engine/API normal-path tests: **2 passed**, 4.09 s.
- New UI normal-path tests: **2 passed**, 3.62 s.

## Boundary findings and fixes

1. Sample delta incorrectly subtracted counts when the analysis unit or evidence source changed.
   Reproduction: **2 failed, 27 passed**, 0.15 s (`boundary-red.log`). Delta is now unavailable in this case;
   exact original/current targets remain in snapshots and the reason is shown. Identical unit text cannot
   independently verify that real measurement scope stayed comparable.
2. A delayed successful amendment response overwrote a newer revision already loaded in the editor.
   Reproduction: **1 failed, 2 passed**, 2.43 s (`ui-red.log`). An initial fix refetched detail data, but an
   added network-latency case showed that background refetch could discard a newer unsaved draft:
   **1 failed, 10 passed**, 5.42 s (`ui-draft-red.log`). Final fix never copies save replies into a detail
   cache; only the still-mounted submitting editor requests a refresh. Abandoned requests refresh the list
   without replacing another editor's saved view or draft. Regression checks preserve both revision 3 and
   its unsaved title when a revision-2 response arrives late.
3. The first full frontend build caught use of `Array.at()` and `String.replaceAll()`, which are not available in the repository's configured TypeScript target. Replaced them with bounded index access and a global replacement regex in the component and fixtures; the repository target was preserved. Focused UI tests and all frontend required checks are rerun.
4. UI hardening requires a deliberate data-stage selection for a new record instead of defaulting to
   unseen/uncollected outcomes. This is a declaration, never independent evidence of prospective timing.

The first boundary command was accidentally launched from the repository root (no root pytest environment);
it executed no tests. The corrected backend-directory invocation produced the recorded failures above.

Covered boundaries: blank/control/Unicode/multiline text and lengths, unknown/missing fields, integer
sample bounds including Boolean/nonfinite/fractional values, malformed IDs/reasons, naive timestamps,
round-trip canonical serialization, original snapshot isolation, changed/reverted fields, stage-only updates,
no-op and backward-stage rejection, hash/parent/sequence/identity corruption, negative sample deltas,
spreadsheet-safe text and numeric CSV fields, complete JSON export, 50-revision/100-protocol limits,
source-size guard, idempotent creation including retry after amendments, stale head exports/updates,
concurrent amendment winner, cross-process lock, failed atomic replacement and recovery, deleted projects,
corrupt record isolation, UI pending controls, uncertain save retry, explicit conflict reload, delayed
responses/navigation, export cleanup and failures. No unsaved draft is included in exported history.

Post-fix focused validation: **38 backend tests passed**, 7.33 s (`boundary-green.log`);
**12 UI tests passed**, 4.52 s (`ui-final-focused.log`).

## Full required verification

Feature commit: `4ac56925`; integration snapshot: `a1eb7e1b3bb501ccfb3b0e8c559d24c950d935fa`; final code snapshot after ES2020 fixes: `c8af5ffece7192cd321bdecfaa75dc72922acf44`.
The final compatibility commit changes frontend files only; the backend tree is identical to the full-test snapshot.
Fetched main/edge `1c908e9e` and scenarios `ac90b1d3` were merged before these checks; prior operator work
and photographic assets remain ancestors. The second merge was conflict-free. Backend contains the new
plaza formats; frontend includes capture lifecycle and shopper motion fixes.

| Command | Result |
|---|---|
| backend `uv run pyright src/` | 0 errors, 0 warnings |
| backend `uv run python -c "from store_emulator.server.main import app; print('OK')"` | OK |
| backend `uv run pytest --basetemp=/workspace/.verification/twinstore-protocols/pytest-full` | 10,571 passed, 1 skipped, 432.95 s |
| frontend pnpm 10.33.0 `build` | Passed after ES2020 compatibility fixes; Vite 28.91 s |
| frontend pnpm 10.33.0 `lint` | 0 errors, 19 pre-existing warnings; none in new module files |
| frontend pnpm 10.33.0 `test` | 1,642 passed / 114 files, 113.71 s |

Frontend uses `npm exec --yes --package=pnpm@10.33.0 -- pnpm ...`, matching the repository pin. Logs live
under `/workspace/.verification/twinstore-protocols/`: `pyright.log`, `boot.log`, `pytest-full.log`, `final-build.log`,
`final-lint.log`, `final-frontend.log`, plus the focused red/green logs named above. `git diff --check` passes.
Original build failures are retained in `build.log`; the focused UI compatibility run passed 12 tests in
4.23 s (`ui-compatible.log`) before the final whole-suite run. Existing build chunk-size and plugin-timing
notices remain. The optional GroundingDINO model test requires explicit opt-in, capture extras and about
700 MB of downloads; no live model run was added for this module.

The old `/workspace/parastore` checkout is clean and was not modified. Destination `origin/feat/operator-modules` was re-fetched and remains `bc6e941a`, an ancestor of the
validated result. Publication uses a normal fast-forward push; no force push or deletion.

## Limitations

A self-hosted local ledger is not external preregistration, trusted timing, a signature or permanent registry.
Anyone with file access can replace it and recompute hashes. Hashes detect inconsistent retained contents;
they do not prove authenticity, authorship, no deleted tail revisions or that outcomes were unseen. App writes
are locked and atomic; external filesystem editors are outside that concurrency protocol. Users should retain
exports/backups and use an appropriate external registry where registration is required.

No live models, actual store data or device/browser usability study. React behavior is verified with jsdom,
real HTTP routes/application storage with TestClient, and file locking also with a separate Python process.
No power estimate, p-value, confidence interval, causal effect or staff performance ranking is inferred.
Next different-domain candidate: dated inventory-cost snapshots or verified shelf price-label reconciliation.
