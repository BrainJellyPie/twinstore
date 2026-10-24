# Keep exit navigation and recorded visit boundaries consistent

A model action could specify nav=leave together with action=enter. Route merging
treated it as the exit and walked to the exit, but timeline construction handled
the enter label first. It replaced the arrival description and omitted the final
EXIT event, leaving a completed visit ending with MOVE.

Timeline construction now handles exit navigation before the enter-label branch,
matching routing precedence. Normal arrival handling, purchases and checkout
ordering remain unchanged.

Offline verification:

- A seeded probe of 800 model-response combinations found 78 missing-boundary
  cases. Inputs combined conflicting navigation/action labels, absent/outside
  coordinates, reversed/outside wandering areas, duplicate control actions,
  unknown SKUs, invalid quantities and boundary dwell values.
- Six narrowed regressions failed before the fix: nearest/planned ordering with
  no purchase, planned purchases or impulse purchases. They verify exactly one
  arrival and exit, the exit location, retained arrival description, correct
  spend and checkout timing.
- All 800 seeded combinations pass after the fix, including purchase consistency,
  chronological events, quantity limits and at most one payment before exit.
- 119 focused model-action, timeline, checkout-target and impulse-checkout tests
  passed in 0.67 seconds. Strict Pyright: zero errors.

Scripted model responses were used throughout; no model services were called.
