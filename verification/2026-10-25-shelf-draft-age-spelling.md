# Preserve shelf-test age quotas across known label spellings

Shelf-test drafts rejected otherwise valid model responses with labels such
as " 30S " or "60S+". The age list now uses the existing unique-identifier
normalization for case and surrounding whitespace. The prompt lists the six
exact supported labels. Unknown age choices and malformed list entries are
still rejected; null or empty lists retain the existing unrestricted quota.

Twelve pre-fix HTTP failures cover all six ages and JSON/JSON Schema modes.
After normalization, real LiteLLM/Instructor responses retain the selected
shelf, SKU and change; constructing ShelfTestRequest and applying the real
quota selects only the requested age from a panel spanning every supported
age and gender. Repeats reuse cache and stores/personas remain unchanged.
Nine malformed-value controls, two unspecified-quota controls and a mixed
spelling public API case are also included.

Focused age, location, optional-field, design-boundary and API suites:
127 passed in 4.05 seconds. Full-source Pyright: zero errors and warnings.
The provider replies were scripted; no native model runs, downloads, paid
calls or native-model error-rate measurements were performed. Existing
LiteLLM logging cleanup warnings remain.
