# Visit clocks outrank unrelated customer timestamps

A table containing `customer_registered_at` and `transaction_datetime` used whichever column
appeared first when both parsed completely. Reversing column order changed the same receipts
from Monday at 17:00 to the previous year's Sunday at 08:00. A more complete registration
column also overrode usable but partially missing transaction timestamps.

Traffic extraction now ranks recognized transaction/visit time labels ahead of unrecognized
timestamp columns. Recognized split date/time pairs receive the same priority. Parsing coverage
still decides between candidates in the same priority group, and every candidate still needs
the existing 80% usable threshold and explicit clock evidence. An unrecognized timestamp remains
a fallback when no recognized candidate qualifies. Conflicting recognized clocks remain subject
to the existing coverage/column-order tie behavior; this change does not infer their semantics.

- Offline direct reproduction: reordering columns alone changed all five test visits' day/hour.
- Before: 30 failed, 9 passed in 0.84 seconds.
- After: 186 passed in 3.39 seconds across named clocks, receipt row order, identities, encodings,
  timezone offsets and split timestamps. Coverage includes Korean labels, 80% completeness,
  midnight, CSV and XLSX. No model calls.
- Strict Pyright for `application/supplemental.py`: zero errors/warnings.
- No full suite or frontend changes.
