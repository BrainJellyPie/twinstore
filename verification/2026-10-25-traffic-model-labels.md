# Validate traffic identities before building customer instructions

The traffic prompt required types from the trade-area identity list, but its
schema and runtime validation accepted arbitrary strings. Those strings were
cached and inserted into per-customer instructions. A customer model following
an unknown type then failed the next stage's identity validator on every retry;
the retries never corrected the earlier traffic response.

Bind the application traffic schema to the supplied identities, using inline
enum constraints for grammar-capable local servers. Validate active-hour types
before caching or creating customer requests. Exact labels retain priority;
case-equivalent labels normalize only when the match is unique. Unknown and
ambiguous labels use the existing three-attempt traffic retry limit. Empty or
blank type lists retain the trade-area fallback, empty identity pools use
`shopper`, and inactive legacy rows retain existing zeroing/ignore behavior.
Direct callers that omit identity choices keep the prior generic schema.

The 36 real LiteLLM/Instructor HTTP cases cover both JSON modes, positional and
explicit clocks, wholly unknown/mixed/ambiguous types, corrected replies,
exhausted retries and invalid cached traffic. A scripted downstream model echoes
the customer type it was instructed to use. Tests require repair in the traffic
stage, no downstream requests after unresolved traffic failure, correct customer
identity/hour/count, and cache reuse without another request.

Eight additional checks cover whitespace, Korean labels, exact case-colliding
labels, empty pools/lists, input preservation, inline schema choices and inactive
legacy rows. All 44 new checks failed before implementation in 4.64 seconds;
eight of those failures were for the newly introduced schema argument.

The focused traffic, identity, fallback, slot and source-context suite passed
223 tests in 8.29 seconds, with no warnings. Full source Pyright reported zero
errors and warnings. No native inference, model downloads or paid APIs ran.
HTTP fixtures verify pipeline behavior, not real-model response accuracy.
