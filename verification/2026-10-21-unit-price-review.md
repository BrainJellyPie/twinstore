# Observed unit-price review — verification (2026-10-21)

## Scope and behavior

New **Market → Unit prices** UI, project-scoped multipart API and deterministic layered calculation module.
User-supplied offers are normalized by pack count and quantity, with exact rational comparisons within an
operator-asserted comparable group, currency and base dimension. Only public, in-stock observations within
the inclusive explicit age window qualify. All source rows and exclusions remain reviewable/exportable.
Comparison uses each side's lowest eligible observed offer, lists exact ties and eligible counts, and never
calls this an optimal price, typical market price, assortment census or demand/causal sales estimate.

CSV source SHA-256, exact rate/gap fractions, scope, raw input and calculation version support reproducibility.
Export requires the reviewed source hash. The module is read-only and unsaved, so there is no shared revision
to overwrite: source changes reject, project deletion rejects, and concurrent independent requests don't write.
The UI locks scope controls during requests, clears results after edits, keys by project and drops late export
callbacks after unmount. Negative generated values stay numeric; operator text is spreadsheet-escaped.

Research/selection is recorded in [candidate comparison](2026-10-21-unit-price-candidates.md).
Prior completed inventory, field-pilot and synthetic factorial modules were inspected and preserved.

## Basic stage, before boundary testing

- `uv run pyright src/`: 0 errors, 0 warnings.
- New engine/API normal-path tests: **3 passed**, 3.73 s.
- New UI tests: **2 passed**, 3.48 s, pinned pnpm 10.33.0.
- No live model calls or actual store datasets were used.

## Separate boundary stage and reproduced fixes

First boundary run: **4 failed, 46 passed** (0.34 s). Log:
`/workspace/.verification/twinstore-unit-prices/boundary-red.log`.

1. `item` quantities incorrectly accepted 0.001, 0.5 and 1.5. Fixed with domain validation requiring whole
   per-pack item counts while allowing fractional mass/volume. Regression tests cover all three failures and
   API rejection, with corresponding UI/docs guidance.
2. CSV text escaping added an apostrophe to a computed negative price gap (`'-200`), preventing normal
   numeric reuse. Fixed by restricting escaping to untrusted identifier columns; calculated signed numbers
   and exact fractions retain their values. Regression checks also retain protection for `=`, `@`, and `-`
   in user labels.

Post-fix focused validation: **54 backend tests passed**, 4.88 s; **9 UI tests passed**, 2.59 s.
Logs: `boundary-green.log`, `ui-boundary.log` in the same directory.

Covered boundaries:
- Empty/header-only/extra/missing/duplicate columns, malformed quoting, invalid UTF-8, BOM, quoted Unicode IDs,
  controls/outer whitespace/length limits, wrong field counts; reordered headers remain accepted.
- Zero, negative, missing, nonfinite, exponent/fractional integer inputs, decimal precision and upper limits;
  smallest/largest valid quantity/price combinations, tiny positive rates and near-equal exact comparisons.
- Exact pack equivalence in g/kg and ml/l; independent currency, product group and mass/volume/item dimensions;
  input order invariance, tied minima, multiple offers per retailer, same ID across different retailers.
- Duplicate retailer/offer observation rejection, unknown focal retailer, inclusive stale cutoff, future dates,
  leap day, same-day window, unknown/out-of-stock/conditional exclusions and combined reasons.
- Missing comparator remains unknown; valid zero-price observations and zero percent denominators.
- 2,000 rows accepted / 2,001 rejected; API exactly 2 MB reaches validation, over 2 MB returns 413.
- Source-hash mismatch 409, project deletion 404, request bounds 422, malformed inputs 400, independent
  concurrent previews, metadata/storage unchanged.
- Pending inputs, scope edit invalidation, file cancellation and limits, network failure recovery, tiny signed
  values, explicit exclusions, CSV request scope/hash, URL cleanup, export error and late unmounted responses.

An initial shell test-append command used a duplicated backend path and wrote no tests; its normal-path-only
run was not counted as boundary coverage. The corrected boundary run above produced the recorded failures.

## Full required checks

Pending at the time of this draft; completed results and final integration snapshot will be recorded before push.

## Limits and next candidate

Source-based requirements hypothesis only: no retailer interview, market validation, live competitor feed,
real-store observations or browser-device usability study. Unit counts are indivisible; unsupported customary
units need deliberate conversion before import. Product equivalence, prices, taxes, deposits and eligibility
remain operator assertions. Dates are calendar observations, not continuous monitoring. A review is not saved;
retain original CSV and audit. Display values round to 12 significant digits; exact relation/ties use fractions.
Currency codes are syntactically validated, not verified against an exchange-rate/ISO service.

No p-values, repeated significance testing or staff/shift pooling; changing date windows is descriptive filtering.
No claim of actual sales impact. The next different-domain candidate is a prospective research protocol and
amendment ledger with immutable history (not a claim of external preregistration).
