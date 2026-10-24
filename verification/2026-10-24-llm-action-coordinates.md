# Preserve strict JSON coordinates after internal-field filtering

The internal-action-field change in `b02269a0` introduced a regression: its
before-validator returned Python containers, so strict JSON validation no longer
converted `target` and `area` arrays into the domain's tuple fields. Instructor
rejected ordinary coordinates even though the equivalent dictionary-based tests
passed. The prior HTTP cases omitted coordinates, so they did not catch it. A
subsequent full three-stage HTTP test exposed the error before the next change
was published.

When validating JSON, the same boundary now converts only coordinate arrays to
tuples before continuing normal validation. Length and integer-element checks
remain strict; other inputs and domain actions are unchanged. The existing HTTP
matrix now includes target, face and wander-area fields, plus sixteen strict
dimension/type cases covering both model stages.

All 24 coordinate-focused cases failed before the repair. Afterward, 113 focused
coordinate, hidden-field, action-boundary, offline-engine and selected-offer
checks passed in 2.62 seconds. JSON and JSON-schema HTTP modes, existing cache
normalization, malformed dimensions, booleans, strings, fractions and null
coordinates are covered. Strict Pyright reported zero errors. Seven existing
LiteLLM asynchronous logging cleanup warnings occurred. No live model calls or
weights were used.
