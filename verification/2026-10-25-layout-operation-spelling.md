# Preserve applicable edits when model choice spellings vary

Model-written layout edits and A/B variants rejected operation kinds such as
`Price`, `PrOmO`, and uppercase `CATEGORY_PRICE` with surrounding whitespace.
This also stopped the existing unused-null handling from identifying which
text fields were irrelevant. A/B engine values `Rule` and ` VLM ` independently
failed, even when the requested operations were valid.

The shared model-draft base now canonicalizes a known operation kind before
validating its fields. Only case and surrounding-space variants are recovered
through the existing unique-identifier helper. Each subclass's literal choices
still reject unsupported operations: package replacement remains unavailable
for saved-layout edits. The A/B draft similarly recovers known `rule` and `vlm`
choices. Prompts explicitly request lowercase operation kinds and underscores.
No domain or direct-save API contracts changed.

The existing HTTP effect matrix now covers all five layout operations and six
A/B operations in JSON and JSON-schema modes, using exact, title-case and
uppercase/whitespace spellings. These 66 cases retain nulls in unused fields
and verify prices, discounts, signs, shelf moves, image replacement, selected
engines, source-store immutability and cache reuse. Required text remains
invalid when null, and malformed unused text remains invalid for every
spelling. Unknown kinds, unknown engines, wrong types and package edits on
saved layouts remain rejected. The full draft-to-save API flow now uses mixed
case and padded model kinds and still verifies source hashes, unchanged source
layout, final prices/reference prices, signs and the newly saved layout.

Before the operation-kind fix, the focused new cases had 45 failures and 72
passes in 9.56 seconds. After that repair, a separate probe of 24 A/B cases
reproduced the engine-spelling failure; those cases overlap the initial matrix
and are not additional distinct defects. The final focused regression suite
passed 289 checks in 9.30 seconds, with 114 known LiteLLM logging-cleanup
warnings. Full source Pyright reported zero errors and warnings. Tests used
scripted HTTP responses and real edit conversion/application/API persistence,
without native model inference, model weights or paid calls.
