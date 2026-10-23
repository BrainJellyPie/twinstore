# Isolate unusable shelf-price readings

Price conversion rounded an infinite scaled value or selected a minimum from an empty candidate
set. A single numeric model reading such as USD 0.001, infinity or 1e308 could therefore abort
`build_items` after the rest of the shelf had been recognized.

Reject nonfinite readings/scaled values and return the existing unreadable-price result when no
positive minor-unit candidate survives. The existing pipeline then preserves the product and marks
its category-based fallback as estimated. When a known category price supports a thousand-unit
abbreviation (e.g. KRW 0.5 meaning 500), keep the surviving candidate even if the literal rounded to
zero. Without a category-price reference, no abbreviation is inferred.

Evidence:

- Exploratory numeric/label/currency/reference matrix: **648 combinations**, **76 exceptions** on
  the old code (36 overflow errors and 40 empty-minimum errors).
- Four offline two-product pipeline reproductions all failed before the fix (0.75s). After the fix,
  the affected product retains an explicitly estimated price and the good product keeps its read price.
- Focused verification: **680 passed in 1.54s**. Includes the full matrix, explicit unreadable values,
  zero-literal abbreviations, known tag precedence, and existing capture/category-price behavior.
- Strict Pyright on the changed module: **0 errors**.

No paid model calls, full suite, frontend or release changes. Existing rounding rules, zero-price
interpretation, typical-price disclosure and general money range are unchanged.
