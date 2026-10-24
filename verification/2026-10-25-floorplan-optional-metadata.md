# Keep valid floor plans when optional metadata is unknown

Local-model floor-plan replies with valid outlines and fixtures were rejected
when an unreadable dimension or fixture label was null. This prevented store
import even though these fields already supported unknown values through zero
dimensions and empty labels.

Normalize only null dimensions to zero and null labels to empty strings.
Clarify these defaults in the prompt. Preserve both known dimensions exactly;
unknown or partially known dimensions retain the existing 12-metre long-side
inference from the actual image aspect ratio. Geometry, fixture kinds,
negative/nonfinite dimensions and malformed nonnull labels remain strict.

Before the fix, 10 cases failed and 17 controls passed in 3.33 seconds.
Scripted HTTP tests exercise both JSON modes, independent missing dimensions,
both unknown dimensions, a known scale with unknown labels, omitted fields,
Unicode labels, store stocking, layout validation and cache reuse.

After the fix, 167 focused floor-plan checks passed in 5.30 seconds. Pyright
reported zero errors and warnings. The 38 pytest warnings are existing
LiteLLM async logging cleanup warnings. No native model inference was used.
