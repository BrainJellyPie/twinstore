# Customer arrival-hour boundaries

Saving customers with arrival hours -1, 24 and 100 returned HTTP 200. The simulation's opening-hours
filter then discarded all of those customers. `Persona.arrival_hour` now enforces its documented
0–23 range, causing invalid save requests to fail before overwriting customers or project metadata.
Existing integer-string coercion remains compatible.

- Seven invalid numeric/string hour cases failed before the fix; six valid boundary save/admission
  cases passed (**7 failed, 6 passed in 3.19s**, other tests deselected).
- Customer-save/identity, simulation opening-hour, town-visitor and generated-traffic modules:
  **97 passed in 4.53s**. Valid hours 0, 1, 22 and 23 survive save/reload and simulation admission.
- Strict Pyright on `domain/persona.py`: **0 errors**.

No live model calls, full suite, frontend changes or release binary changes. Existing invalid saved
customer files are not rewritten; loading them now fails validation instead of producing invalid clocks.
