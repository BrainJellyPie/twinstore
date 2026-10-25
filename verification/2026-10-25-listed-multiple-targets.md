# Reject separate target names instead of selecting the longest

The shared name resolver accepted the longest complete name anywhere in a
model field. A shelf-test answer such as `Tea or Premium Coffee` could therefore
apply Tea's requested price to Coffee. Store-format and category drafts could
also select a different target silently.

Exact complete names and bounded long-name recovery remain unchanged. For a
copied description, the resolver now distinguishes a shorter name contained
inside a full longer name from separate or overlapping mentions. Every
remaining mention must identify the same value. Ambiguous shelf-test targets
enter the existing correction attempt; setup and category drafts retain their
existing warning and partial-draft behavior.

Regression cases cover unequal lengths, separate nested names, overlapping
names, Korean names, repeated mentions, aliases, exact-name priority and
reversed catalog order. Real LiteLLM/Instructor HTTP tests exercise corrected
and permanently ambiguous answers, cached reuse and unchanged source stores.
The former format test expecting `Tea and Steak` to select Steak is corrected:
name length provides no evidence that the model intended that format.

Before repair: 13 failed, 29 passed in 2.66 seconds. After repair: 145 focused
resolver, shelf-draft, layout-brief, shopper-filter and optimization tests pass
in 4.94 seconds. Full-source Pyright reports zero errors and warnings. Tests
emit 12 existing LiteLLM logging coroutine warnings. No full suite, paid calls,
model weights or native inference were used.
