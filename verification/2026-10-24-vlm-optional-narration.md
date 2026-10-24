# Preserve valid vision choices with absent optional text

An entry plan with a valid purchase could fail the entire shopper when a local
model returned null for an optional mission, reason, category or product string.
Shelf glances similarly discarded a valid numbered choice when product text or
reason was null. These fields already default to empty strings when omitted.

Their existing before-validators now normalize only null to the same empty-string
value, before applying the unchanged text bounds. Both prompts explicitly request
empty strings for absent text. The JSON schema remains a bounded string grammar.
Integer, list and object values still fail validation; null enter/items/quantity,
badge number and interest remain invalid. Product matching, raw-photo restrictions,
budgets and retry bounds are unchanged.

Before the fix, 20 HTTP regressions failed and 23 invalid-type controls passed.
Final focused verification passed 214 tests in 3.70 seconds, with zero strict
Pyright errors. The new HTTP paths cover JSON and JSON_SCHEMA, text-only and image
entry plans, actual canonical purchases (two 700-unit items), original vision-plan
provenance, valid badge resolution, and one-request cache reuse. Existing clipped
name/category, badge, truncation and invalid-choice checks also passed. Twenty-nine
existing LiteLLM logging-cleanup warnings occurred. All responses and transports
were scripted; no live or paid inference was used.
