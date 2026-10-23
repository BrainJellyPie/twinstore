# Conjoint signed-seed completion

`ConjointRequest` accepts signed integer seeds. Panel selection and task design already
handled them, but NumPy bootstrap initialization rejected a negative seed after model
responses had been collected. The API reproduction collected 20 respondents / 120 choices
and then marked the study failed.

Estimation now uses `abs(seed)`, matching A/B and shelf-test bootstrap conventions. This
does not change panel/task generation or the stored request; nonnegative seeds are unchanged.
The same fixed answers yield the same estimates for opposite seed signs.

Boundary coverage includes -1, the signed 64-bit boundary, a negative 81-digit integer,
zero, prices absent/present (including a free level), and none-of-these enabled/disabled.
Finite serialized estimates and repeated-seed equality are checked. The API test covers
completed reports, CSV/HTML exports and deletion using a fake model.

- Before: 13 failed, 5 passed in 3.82 seconds.
- After: 313 passed in 4.58 seconds across seed boundaries, conjoint design/estimation,
  convergence and the two fake-model API cases.
- Strict Pyright for `engine/marketing/conjoint.py`: zero errors/warnings.
- No live model calls or frontend changes; no full suite run.
