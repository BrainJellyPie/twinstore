# Bound raw action time before scenario scaling

Combining extreme model durations with scenario multipliers exposed two problems with bounding
area time in route sanitization: float multiplication could already have overflowed in the runner,
and a legitimate increase from 120 to 240 seconds was cut back to 120 afterward.

CustomerAction now normalizes parsed dwell integers to the prompt's existing 0–120-second range.
Its response schema advertises the same bounds. This happens before scenario arithmetic and
accepts out-of-range model integers without another paid retry. Internally scaled action copies
retain their computed durations, so scenario increases and decreases are preserved. The route-level
clamp was removed; rack-specific dwell resolution remains unchanged.

Focused offline evidence:

- Full runner comparisons against zero-dwell controls, with 0.5×/1×/2× scenarios and negative,
  zero, boundary and enormous times: **11 failed, 16 passed in 1.44s** before repair.
  An initial test assertion used a nonexistent summary field; it was corrected to `avg_visit_sec`
  before recording this baseline.
- JSON response parsing for every action kind, schema bounds, area geometry/continuity,
  model action framing, scenarios and fake VLM planning: **335 passed in 20.64s**.
- Strict Pyright on the changed domain and route modules: **0 errors**.

The full-run checks use a scripted engine and no model providers. No full suite, frontend or
release changes. Historical saved timelines are not rewritten.
