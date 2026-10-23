# One operating window per weekday

## Reproduction and change

Two Monday schedule entries were accepted. Offline generation then produced 40 customers with only
20 distinct IDs while saving a 20-visitor estimate. A closed Monday followed by an open Monday also
made `open_days` report an open day while `is_open_at` rejected its arrivals.

Use shared domain validation for unique weekdays in saved stores, wizard requests, direct project
creation and customer generation. The background worker validates old metadata before starting the
model or supplemental analysis. Repeated entries, including disjoint windows and open/closed conflicts,
are rejected because the current schedule contract supports one window per weekday. No silent merging
or arbitrary first/last-entry choice. Counting is linear for oversized invalid lists.

## Focused evidence

- Covers every weekday and identical/split/closed conflicts; numeric and string representations of
  the same weekday; empty, partial and reordered valid weeks; a seven-day population with unique IDs.
- API creation rejects before any project write or generation call; rejected edits preserve the file.
  Direct creation and background jobs with old metadata reject before model calls and preserve data.
- Before the fix: **35 failed, 5 passed in 3.88s**.
- New cases plus opening-hour, template-schedule, missing-day and project-template modules:
  **415 passed in 10.54s**. Replaced the initial duplicate scan with linear counting and added a
  100,000-entry rejection case; the affected engine module then **30 passed in 0.24s**.
- Strict Pyright on all five changed production modules: **0 errors**; domain module rechecked after
  the linear-counting change, also **0 errors**.

No full suite, live model calls, frontend changes or release binary changes. Old conflicting files are
rejected, not automatically rewritten. Overnight/multiple-window schedules remain unsupported.
