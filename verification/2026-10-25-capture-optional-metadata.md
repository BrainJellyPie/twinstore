# Partially readable shelf labels

A missing text value represented as null rejected a whole shelf label,
discarding readable product and price fields. Actual crop-label HTTP requests
and group processing reproduced fourteen failures; twenty-one omitted-field,
malformed-type and confidence controls passed in 2.69 seconds.

The model-label schema uses its existing empty-string defaults for null name,
brand, size, category and price-tag text. The prompt asks for that representation.
Numeric price and confidence validation are unchanged. A readable name (or the
existing brand fallback) retains its recognized status and exact price; when
both are unreadable, the product remains explicitly unrecognized.

Tests cover the real image-crop request, group failure handling, progress,
planogram item construction, 249-cent price conversion, facing geometry and
cache reuse in both JSON modes. No missing name, confidence or price is invented.
No native model or paid inference was run.

Focused validation: 111 passed, 1 skipped in 7.17 seconds. Pyright: 0 errors,
0 warnings. The skipped native detector test requires GDINO and explicit opt-in.
