# Do not erase numeric comma meaning in POS imports

The numeric reader removed every comma before calling `float`. Decimal-comma quantities such as
`0,5` therefore became `5`, and malformed grouping such as `1,,234` was silently accepted as 1234.
The same conversion affected unit prices, line totals and optional hours, corrupting fidelity inputs.

Commas are now removable only in a complete thousands-grouped number: an optional sign, one to
three leading digits, one or more three-digit groups, an optional decimal-point fraction and an
optional exponent. Other comma forms raise the existing numeric-input error with format guidance.
The application already maps that error to HTTP 400. Invalid optional hours retain their existing
unknown-hour behavior. The established interpretation of `1,250` as 1250 is preserved.

Focused offline evidence:

- Baseline **67 failed, 18 passed in 1.10s** across CSV/XLSX, quantity/unit-price/line-total columns,
  decimal commas, repeated/misplaced grouping, exponent punctuation, refunds and valid forms.
- POS parsing, receipt scopes, calendar evidence and fidelity checks: **652 passed in 2.73s**.
  Changed parser module strict Pyright: **0 errors**.

No model calls, full suite, frontend or release changes. This does not infer a numeric locale from
currency, nor convert decimal-comma imports automatically; the error asks for decimal points.
