# Separate reused POS receipt numbers in fidelity reports

## Reproduction and fix

Three independent one-item receipts shared number `001`: Monday at register R1, Tuesday at R1 and
Tuesday at R2. Against three identical simulated baskets, the report counted one real transaction,
reported mean-basket ratios of 0.333333 and a basket-value distance of 600 instead of zero.

Add an optional tuple of receipt-scope fields to `PosLine`, preserving its original transaction ID.
The importer records recognized store/register/terminal identifiers and an explicit local calendar
date from timestamp/date columns. Fidelity groups on both original ID and scope. Different seconds
within the same receipt do not split its product lines. Time-only/unknown values never borrow the
import's execution date. Existing callers without scope retain their previous grouping.

## Focused evidence

- CSV/XLSX matrix covers timestamp/date, store, register, terminal, till and branch scopes, leading-zero
  IDs, combined date/register resets, per-line seconds, local UTC offsets, normalized numeric date
  formats, missing/time-only dates and delimiter-like text in identifiers.
- Before the fix: **24 failed, 1 passed in 0.92s** (several checks require the newly added scope field).
- New cases plus POS validation, analysis, returns, receipt-review and receipt-currency modules:
  **416 passed in 1.42s**.
- Strict Pyright on the two changed modules: **0 errors**.

No live model calls, full suite, frontend changes or release binary changes. Existing report files
are not rewritten. Scoping uses recognized columns and explicit numeric calendar dates; it cannot
separate receipt-number reuse when an export omits every distinguishing field.
