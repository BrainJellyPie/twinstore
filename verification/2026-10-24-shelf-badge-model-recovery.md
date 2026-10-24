# Constrain shelf-test responses to visible badges before caching

Shelf tests checked selected and noticed badge numbers after the structured model
response had already been cached. A local model selecting an invented number
therefore produced an invalid pair that the same rerun could repeatedly retrieve
from cache. The provider's grammar also had no knowledge of the visible numbers.

Each image now gets a response schema with exact allowed badge enums for pick and
noticed. The prompt lists those same numbers. A request-local validator enforces
membership even when a server ignores schema constraints. Empty images allow
pick zero and a zero-length noticed list, without emitting an impossible empty
item enum. There is one correction attempt; only validated answers are cached.
Repeated failures remain errors, and never become purchase refusals or valid
pairs. Existing duplicate-notice normalization remains unchanged.

Thirty mocked HTTP cases exercise normal, sparse and empty badge sets with an
out-of-range pick, huge pick, unknown notice, zero notice or negative notice,
both with successful correction and repeated failure followed by a later retry.
The actual OpenAI/LiteLLM/Instructor path verifies outgoing enums, request counts,
cache exclusion/reuse, SKU resolution and paired comparison eligibility. Existing
controls cover no purchase, duplicate notices, per-arm membership, empty images,
concurrency and all-invalid job failure.

Before: all 30 cases reproduced. After: 60 focused checks passed in 8.13 seconds.
After a schema type-annotation adjustment, all 48 engine checks passed again in
3.51 seconds; strict Pyright reported zero errors. `git diff --check` passed.
HTTP and image rendering in the new matrix are mocked; no live inference or paid
provider calls were used. This establishes protocol behavior, not model accuracy.
