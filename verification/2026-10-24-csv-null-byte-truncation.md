# CSV NUL truncation

Pandas' CSV reader silently ended cell values at a NUL character. A direct probe
read receipt IDs `001<NUL>A` and `001<NUL>B` as the same `001`, changed
`tea<NUL>wrong` to `tea`, and read `3<NUL>00` as price 3. Customer-data imports
used the same reader and could merge separate visits. The prior CSV structure
check did not reject these characters.

The shared CSV validator now rejects NUL in decoded text before any downstream
table/point allocation. The error identifies the CSV and requests a fresh text
export. No stripping or repair guesses alter the supplied values. Checking
decoded text preserves normal BOM-marked UTF-16/UTF-32 files, whose encoded bytes
contain zeros as part of legitimate characters. Literal `NULL`, visible control
symbols, quoted multiline notes and ordinary separators remain supported.

175 focused CSV import, allocation, encoding and API checks passed in 4.21
seconds; the four POS API cases passed again after making byte escapes explicit.
Pyright reports zero errors for the changed module. The new unit matrix had 26
failures and four passing controls before the fix. API checks prove no customer
project/generation starts and no existing POS/movement evidence is replaced on
rejection. No full suite, frontend rebuild or paid model calls.
