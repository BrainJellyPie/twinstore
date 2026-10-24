# Do not infer a visit from a missing entry decision

An empty entrance-model response inherited enter=true from the internal plan
model. It was recorded and cached as a successful vision decision. In an
ensemble, one missing response and one explicit walk-out tied the entry vote,
which caused the shopper to enter. The problem occurred from zero-item plans
through the maximum shopping-list size.

Require enter only in the response models returned by entry_decision_model,
including the full-size branch. Preserve internal EntryDecision defaults,
item trimming, explicit true/false decisions, optional narration and the
confirmed-walk-out null-list handling. No retry budget increases. Missing
decisions now use existing failure handling and are excluded from valid votes.
The prompt explicitly requests the boolean decision even for an empty list.

All 38 regression cases failed before the fix in 3.32 seconds. Scripted HTTP
covers both JSON modes, text/image plans, single/voting clients, empty/partial
answers, malformed legacy caches, later explicit walk-outs and cache reuse.
Controls cover all list-limit branches and an all-empty first model response
that must not be recorded as a vision plan. Existing label-clipping fixtures
now include an explicit entry decision. Cache assertions compare response
values because Instructor's fresh response may be a subclass of the cache type.

After the fix, 289 focused entry, walk-out, offer-resolution, clipping,
quantity and truncation checks passed in 5.22 seconds. Pyright reported zero
errors and warnings. The 15 pytest warnings are existing LiteLLM async logging
cleanup warnings. No native model inference or model download was used.
