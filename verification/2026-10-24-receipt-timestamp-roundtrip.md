# Receipt review timestamp round trips

Review accepted `2026-W43-3T14:05`, `2026W433T1405` and
`2026-10-21X14:05`, but the exported POS parser discarded their dates and hours.
This lost hourly evidence and receipt date scope despite successful review.
Compact timed forms such as `2026W43T14` were incorrectly rejected by the
previous string-length test for missing time.

After validating a local timestamp, normalize the copied receipt to a calendar
date and ISO time before CSV export. Use date parsing to recognize genuinely
date-only inputs. Offset-bearing and invalid timestamps remain errors; missing
timestamps remain optional with a warning. Original OCR/edit inputs are unchanged.

Validation: 78 focused receipt review, OCR, currency and API tests passed in
4.41 seconds; Pyright reports zero errors for the changed module. The new 32
cases cover compact/extended calendar and week dates, year boundaries, leap
days, midnight, fractional seconds, separators, offsets and invalid values.
The initial run had 17 failures, including normalization expectations as well
as the reproduced data-loss/rejection cases. No paid calls or full suite.
