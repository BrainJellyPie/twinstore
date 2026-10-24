# Compact intent catalogs without dropping products or offers

The default compact-store template produced a 17,333-token stage-two system prompt
with the offline Qwen tokenizer. It repeated long opaque SKU identifiers and
product text at each facing/level, exceeding an 8K local context before the
customer prompt or output. The urban and campus templates used 27,152 and 34,607
system tokens respectively.

The intent prompt now has one short record per distinct (SKU, name, price,
promotion) offer. Shelf rows refer to those records; identical ordered product
lists share a row listing every represented block, face and level. Existing rack
descriptions, decorations, access tiles, entrance/exit and checkout information
remain. No product, price variant or previously represented placement is removed.
Record prefixes avoid collisions with real SKUs, including user-supplied SKU names
that already look like references.

The request-local action grammar lists the available codes. Its field validator
restores canonical SKUs before the shared client caches a result. Existing real
SKU answers still validate, and existing unknown-SKU filtering remains. A SHA256
digest of code-to-SKU bindings is included in the schema comment/cache identity:
two catalogs that look identical but have different opaque IDs cannot reuse each
other's decoded purchases. The engine converts request-local response classes
back to its stable action model before execution and comparisons. Impulse prompts
and their canonical SKU handling are unchanged.

Production system-prompt measurements are now 5,723 tokens for compact, 9,337 for
urban and 9,848 for campus. These exclude chat templates, customer text, response
schema overhead where included by a provider, and output. The compact catalog now
leaves room within 8K for a normal request; larger catalogs can still exceed 8K.
This patch does not claim that every store fits every server, nor that changing
prompt presentation leaves live model preferences statistically identical.

Twelve new HTTP contract regressions failed before implementation. Final focused
verification covered 331 unique checks: 330 passed in the broad run, and the
remaining test's currency assertion was corrected to the existing 900¢ prompt
format; the final 18-case catalog suite passed in 3.04 seconds. Strict Pyright
reported zero errors. Checks include OpenAI/LiteLLM/Instructor JSON and JSON_SCHEMA
paths, both route orderings, opaque/Unicode/reference-like SKUs, strict coordinates,
canonical cache contents, repeated visits, six independent SKU mappings with
identical visible prompts, concurrent calls, empty catalogs, repeated placements,
name/price/promotion variants, purchase revenue and the existing action guards.
Eight existing LiteLLM logging-cleanup warnings occurred in the broad run. All
responses and transports were scripted; no live or paid inference was used.
