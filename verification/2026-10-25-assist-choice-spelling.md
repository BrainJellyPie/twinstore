# Keep known assistant choices usable without changing their rules

Tool routing, optimizer setup and test suggestions failed when a model changed
the case or surrounding whitespace of a valid destination, objective, scope or
test kind. Their response validators now normalize string spelling before the
existing lowercase literals validate it. Prompts ask for exact IDs including
underscores. Unknown choices, changed internal separators, wrong types and
explicit null operational choices remain errors.

The HTTP matrix covers all 11 destinations, six objectives, three scopes and
three test kinds in both structured-output modes. It uses real LiteLLM and
Instructor with scripted replies and repeated cache reads. Routing is checked
both with and without a run: run questions, shopper search and optimization
still resolve to `none` when there is no run. Optimizer results retain the
selected scope/objective, actual OptimizeSpec direction (walking distance is
minimized), five-move limit, 2% gain and shelf lock. Suggested questions retain
their text/evidence. Store inputs remain unchanged.

Existing API tests add mixed-case replies for routing, optimization and group
interview suggestions, retaining missing-run checks, numeric limits, lock
resolution, deduplication and malformed optional-field controls. Before the
repair, 58 cases failed and 59 passed in 9.33 seconds. The final focused suites
passed 165 checks in 4.84 seconds, with 41 known LiteLLM logging-cleanup warnings.
Full source Pyright reported zero errors and warnings. No simulation study,
native model inference, model download or paid call was run; model error
frequency was not measured.
