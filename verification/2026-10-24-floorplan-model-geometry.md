# Validate model geometry before building a floor-plan store

Floor-plan model responses accepted arbitrary coordinate lists and nonfinite
numbers. An infinite physical width passed response validation and then crashed
grid construction. Malformed fixture boxes were silently skipped, and reversed
or zero-area outlines could distort an otherwise successful import. Invalid
responses could already be cached before these errors were detected.

Constrain each image coordinate to the documented finite 0–1000 range and each
box/outline to exactly four values. Validate the outline's positive extents and
finite nonnegative physical dimensions before caching. Give the vision model one
correction attempt and describe these rules in its prompt. Repeated invalid
geometry remains an error; no fixture is silently discarded for having the wrong
number of coordinates. The existing auto-reader fallback remains unchanged.

Forty-two offline HTTP cases cross 21 invalid geometries with recovery or repeated
failure: missing/extra coordinates, nonfinite and out-of-image coordinates,
reversed/degenerate outlines and invalid physical dimensions. They exercise real
OpenAI transport, LiteLLM, Instructor, response cache and successful store building.
Only corrected geometry is cached; repeated invalid output stops after two
requests. A separate control preserves inferred scale, reversed fixture corners
and zero-height entrances, which the existing normalizer supports.

Before: all 42 initial cases failed. After: 73 focused VLM/classic/PDF reading,
floor-plan API and persistence checks passed in 8.57 seconds; the added valid-edge
control passed with the 43-case geometry suite. Strict Pyright reported zero
errors in the changed module; `git diff --check` passed. No live vision inference
or model download was used.
