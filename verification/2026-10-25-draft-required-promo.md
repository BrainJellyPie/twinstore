# Preserve explicit promotion text in automatic drafts

The automatic layout and A/B proposal mapper replaced an omitted, empty or
whitespace-only promotion with `SALE`. A request for a `1+1` sign could therefore
produce a different promotion while being reported as a successful draft.

Both prompts now require nonblank sign text. The shared draft mapper validates
it after resolving the product, inside the existing response validation and
bounded correction loop. Unknown products still follow their existing warning
and skip behavior. Manually authored variant defaults are unchanged.

Thirty-four new cases exercise actual LiteLLM/Instructor HTTP processing:
layout/A/B drafts, both JSON modes, omitted/empty/whitespace/null values,
corrected and permanently invalid replies, and stale invalid cache entries.
Corrected drafts preserve `1+1` through application and cache reuse without
mutating the source store; persistent failures stop after two attempts and
are not cached. Null was already rejected and remains a control.

Before repair: 26 failed, 8 passed in 3.44 seconds. After repair: 282 focused
draft, unused-field, application and API tests pass in 9.00 seconds. This also
checks mixed drafts containing unknown products. Full-source Pyright reports
zero errors and warnings. The test run emits 68 existing LiteLLM logging
coroutine warnings. No full suite, paid calls, model weights or native inference
were used; scripted responses do not measure model accuracy.
