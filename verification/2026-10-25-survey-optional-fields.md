# Optional null fields in automatic concept-test drafts

A local model returning null for optional images, age groups, genders, context
or rationale rejected an otherwise usable concept-test draft. All five fields
already supported omission with an empty-list or empty-text default. The HTTP
baseline had twelve model-response failures and two cache misses from legacy
null entries; nineteen required-field and malformed-type controls passed.
The baseline took 3.78 seconds in JSON and JSON-schema modes.

Only the generated draft normalizes those optional nulls to its existing
defaults. The prompt asks for empty lists/text and reserves null for an absent
reference price. Missing images still produce review warnings, while the test's
name, questions, exact minor-unit price and other supplied fields are preserved.
Required null fields and malformed non-null values remain invalid.

All 98 focused optional-field, image-resolution, currency-boundary and draft API
checks passed in 3.76 seconds, including cached null entries and repeated draft
reuse. Thirteen existing LiteLLM async-logging cleanup warnings were reported.
The transport was scripted; no model inference or paid calls were used.
Strict backend type checking passed with zero errors; `git diff --check` is clean.
