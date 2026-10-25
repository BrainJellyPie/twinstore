# Preserve planned purchases when the optional shortlist is null

After a valid purchase plan, a long impulse prompt can require a smaller
candidate list. That shortlist already allowed an omitted `codes` field or an
explicit empty list, but `codes: null` failed both model attempts and aborted
the entire shopper. The previously valid planned purchase never reached the
executor.

Normalize null to [] only when the candidate response is optional. The impulse
prompt explicitly requests `codes: []` for no candidates, and the JSON grammar
still asks for an array. The primary shortlist continues requiring an explicit
answer and rejects null. Non-null malformed lists and unknown codes are not
converted into absence. No model calls or purchase actions are added when the
optional list is empty.

Twelve real LiteLLM/Instructor HTTP cases exercise null, empty and omitted
optional lists across both structured modes and route orderings after a context
rejection. They execute the preserved plan, verify two units costing 200, one
payment and an exit, retain the source layout, and check repeated cache use.
Cached optional nulls pass through the same validation. Twelve type/unknown-code
controls and one required-versus-optional/schema control preserve the boundaries.

Before the fix, five tests failed and twenty passed in 3.28 seconds. The focused
optional-candidate, optional-action, missing-primary-selection, code-spelling
and compact-impulse suite passed 162 tests in 10.91 seconds. Full source Pyright
reported zero errors and warnings. No native inference, model downloads or paid
requests ran; the HTTP replies and context rejection are scripted.
