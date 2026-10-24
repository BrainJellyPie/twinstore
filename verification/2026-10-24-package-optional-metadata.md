# Preserve partial package readings

Unreadable package text is optional, but explicit null values from a local vision
model failed validation and discarded the entire result. The package response now
normalizes only null text fields to their existing empty-string defaults, and the
prompt explicitly requests empty text for unknown values without guessing.

The API keeps an existing image name or brand when the corresponding reading is
unknown. An absent store-product match does not invent a SKU link. Confidence bounds
and invalid non-null text types remain unchanged.

Before the fix, all six partial-reading API cases returned 502; two controls passed.
Focused checks now pass 74 cases in 12.01 seconds, including both HTTP structured
modes, each missing field and all fields missing, saved cache values, cache reuse,
canonical product matching, persisted API metadata, invalid types, confidence
bounds and concurrent project/package lifecycle safeguards. Cache comparisons use
serialized response fields, excluding Instructor's response metadata. Strict
Pyright reports zero errors. Eleven existing LiteLLM logging coroutine cleanup
warnings were emitted. All model responses were scripted; no live model was run.
