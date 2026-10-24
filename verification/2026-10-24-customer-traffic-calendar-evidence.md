# Explicit calendar evidence for uploaded customer traffic

## Reproductions

Customer uploads containing `Oct 19 09:00`, `2026-10 09:00`, `2026 09:00`,
`19 09:00` or `09h30` produced visits with a parser-supplied year, month or day.
Two hundred such rows could replace the generated arrival profile with a
misleading weekday distribution. In mixed files, date-only strings also became
midnight visits, and incomplete rows could push 199 valid visits over the
200-visit fitting threshold. Conversely, explicit compact midnight timestamps
were sometimes discarded because clock detection expected a colon.

POS parsing had a related boundary: its two nearby default days both resolved
`2026-10 Mon 09:00` to October 5, falsely proving an explicit date.

## Change

Parse text with different calendar/hour defaults to establish which components
are present before pandas timestamp conversion. Ignore incomplete dates and
numeric cells; retain explicit clocks in compact and textual formats. Exclude
date-only text rows individually even when the surrounding column contains
times. Existing native Excel midnight inference, split date/time handling,
local timezone clocks, named-column precedence and receipt grouping remain.

Separate the default days by more than a week in both traffic and POS parsing,
so weekday names cannot manufacture an agreed day. Cache up to 4,096 distinct
text checks per table; repeated product lines share parsing work, and upload
data is not retained in a global cache. No dependency was added.

## Validation

343 targeted traffic/POS checks passed in 4.35 seconds. The new traffic cases
cover incomplete components, mixed CSV/XLSX rows, date-only rows, compact
midnight, timezone offsets, the 200-visit threshold, native Excel midnight and
repeated-value parsing. POS cases include partial dates with weekday names.
Both changed modules pass Pyright with zero errors. An intermediate test run
required correcting an exact floating-point assertion to an approximate one;
the calculated share was 0.9999999999999998 rather than 1. No paid calls,
frontend rebuild or full suite.

This keeps the existing heuristic that a native Excel datetime column needs
majority non-midnight evidence to distinguish clocks from date-only cells.
Missing-time rows are excluded from fitted traffic, not inferred from filenames
or the date of import.
