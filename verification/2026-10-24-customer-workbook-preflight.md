# Customer workbook preflight

The store wizard previously checked only an XLSX upload's resource budget.
Malformed workbooks passed that check, then reached automatic product selection
and project/customer creation. The later customer reader returned no frames on
failure, so generation could continue without the supplied evidence.

The wizard now runs the same workbook reader used by supplemental summaries and
traffic fitting before any project or model work. Read failures return an
actionable 400 response. Existing resource-limit failures remain 413. Declared
worksheet parts must also exist: openpyxl otherwise silently omits a missing
second sheet and returns the surviving data. Blank workbooks are rejected;
header-only templates and additional blank sheets remain valid.

Validation:

- Before the fix, 18 malformed-file cases reached the guarded automatic-product
  selection stub; four valid controls passed. A separate real ZIP probe showed
  the missing-second-sheet reader returning only its surviving sheet.
- Final API cases cover empty bytes, renamed CSV, truncated ZIP, missing workbook,
  missing first/second sheet, broken first/second sheet XML, invalid numeric cells
  and blank workbooks, with lower/uppercase extensions. They verify no product
  selection, generation or project creation occurs on rejection.
- Valid files retain their bytes and filename for generation and preserve zero-
  padded identifiers; unrelated malformed custom XML remains ignorable.
- All 167 focused workbook resource, wizard, supplemental-format, visit identity,
  split-clock and POS-time tests passed in 6.91 seconds. Strict Pyright passed.

The shared reader still returns the existing empty-result fallback to background
callers. Present formula caches are not recalculated or certified as current.
