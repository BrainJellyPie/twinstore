# Keep a reachable checkout at every imported entrance position

The default counter was placed two tiles to the entrance's right, clamped at
the grid edge. Right-edge entrances therefore shared its tile, and the builder
silently omitted the counter. An explicit counter that mapped to the same
coarse grid tile as an entrance was omitted too. The resulting store warned
that payment was unavailable.

When a counter collides with the entrance, place it nearby, moving inward at
the right border. Keep the existing placement for non-colliding counters and
record a note when an explicit counter needs adjustment. The aisle-connection
repair preserves the resulting counter and makes its service area accessible.

Twenty-two failures were reproduced through model HTTP responses, with 26
controls passing in 3.24 seconds. Both JSON modes cover the four edge midpoints
and all four corners, crossed with missing, colliding and distinct counters.
Tests read the model plan, construct and validate the store, then execute a
purchase, one payment and exit. Cached readings reproduce the corrected layout.

Afterward, 192 focused checkout, dense-access, geometry, reader, API and
persistence checks passed in 9.76 seconds. Pyright reported zero errors and
warnings. The 56 pytest warnings are existing async logging cleanup warnings.
No real model inference or downloaded model was used.
