# Constrain the first starter-category request

The initial category-selection schema accepted any strings as rack/category IDs.
Only the prompt contained the actual choices, so a grammar-capable local server
could still emit invented section IDs while satisfying its JSON schema. The
existing bounded fallback already supplied enumerated choices, but only after
the first grouped request failed and its correction was exhausted.

The initial request now carries request-local category and rack ID enums.
Occupied/inaccessible racks and excluded categories are absent. Sorting the enums
keeps the schema/cache identity stable, while separate concurrent calls retain
their own choices. Membership, exactly-once coverage, category uniqueness and
bounded fallback remain enforced by the existing semantic validation even if a
server ignores the JSON schema. No retry budget or product selection changed.

Before the fix, all 13 new checks failed because the wire/request schema lacked
these restrictions. Afterward, 236 unique focused checks passed: 127 grammar,
repair, decomposition, context-overflow and API recovery checks in 6.63 seconds,
plus 109 placement/API checks in 10.91 seconds (465 unrelated catalog repetitions
deselected). The 13 new checks passed again after the final type-only adjustment.
The cases cover 1/2/7/8/99/100 racks, sparse identifiers, Korean, emoji, quotes,
slashes, case-sensitive names, occupied/blocked racks, category exclusions,
repeat-cache use, and concurrent independent requests. The HTTP cases inspect the
serialized OpenAI request through LiteLLM and Instructor with a mock transport.

Strict Pyright reported zero errors and `git diff --check` passed. No weights,
live model inference or paid calls were used. This verifies the transmitted
constraints and recovery contract, not generation accuracy on a physical model.
