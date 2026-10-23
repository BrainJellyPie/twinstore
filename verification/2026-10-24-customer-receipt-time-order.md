# Customer traffic uses order-independent receipt times

Supplemental visit fitting discarded repeated receipt lines by keeping whichever line came
first. A receipt scanned at 10:59:59 and 11:00:00 could therefore become a 10:00-hour or
11:00-hour visit solely because the export was sorted by product differently. POS fidelity
already used the earliest available receipt hour; customer generation did not.

Visits now use the minimum valid local timestamp within the existing receipt identity
(calendar date, exact receipt ID, and available store/register scopes). Missing optional scope
values remain groups rather than disappearing. A table without receipt identifiers retains
its per-row counting. Caller dataframes are not modified.

- Baseline: 21 failed, 1 passed in 0.79 seconds.
- Related receipt identity, CSV/XLSX, timezone, split-clock, encoding and retry cases:
  147 passed, 6 failed in 5.91 seconds. The six failures were an exact float assertion on
  0.9999999999999998 versus 1, corrected to approximate comparison without changing source.
- Final new boundary file: 22 passed in 0.70 seconds.
- Strict Pyright for `application/supplemental.py`: zero errors/warnings.
- Tests use shuffled product rows, different dates, blank/leading-zero register IDs, native
  timestamps, mixed timezone offsets, split date/time columns and invalid timestamp rows.
- No live model calls, frontend changes or full suite.
