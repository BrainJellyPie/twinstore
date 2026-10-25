# Use the reachable side for an automatic shelf move

Layout and A/B draft schemas choose a shelf and level, leaving its face to the
application. The mapper always picked the face with most products, including
inaccessible products. On a two-sided shelf, a locked, walled or obstructed busy
face made a valid move fail both model attempts even when the opposite face was
open. The model could not correct that choice through its response schema.

Unspecified faces now prefer the busiest existing reachable side. If none is
available, the existing blocked-face warning remains. Explicit face selections
are unchanged. The same blocked-face snapshot also guards full-slot swaps, so
the displaced product must still have an accessible destination.

Forty-eight real LiteLLM/Instructor HTTP cases cover layout/A/B drafts, both JSON
modes, locks/walls/fixtures, empty/full destinations and reversed slot order.
Each valid draft completes in one request, reuses its cache, moves Tea to the
reachable eye-level slot, conserves every product and its properties, preserves
the displaced product's accessibility, and leaves the source layout unchanged.
Six controls retain warnings for explicit blocked faces and fully blocked
existing shelf sides.

Before repair: 48 failed, 6 passed in 8.44 seconds. After repair: 159 focused
automatic draft, displaced-product, move and layout API tests pass in 7.92
seconds. Full-source Pyright reports zero errors and warnings. Tests emit 48
existing LiteLLM logging coroutine warnings. No full suite, paid calls, model
weights or native inference were used.
