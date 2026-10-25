# Do not guess between multiple image names in one survey entry

The survey image resolver previously chose the longest matching library name
from a model-generated description. `Gold or Silver Pack` selected Silver Pack
and retained the proposed reference price without a warning. `Gold Extra next
to Gold` similarly selected Gold Extra despite naming two separate packs.

Exact full names still take precedence. For copied descriptions, shorter names
are ignored only when that occurrence lies within a complete longer name. All
remaining mentions must resolve to one asset identity. Different assets follow
the existing ambiguous-image warning path; an unresolved first image also loses
its reference price. Repeated mentions and aliases of one asset remain usable,
with a deterministic display label. The prompt asks for one image per entry.

Thirty-two real LiteLLM/Instructor HTTP cases cover both JSON modes, reversed
library order, different-length names, separately repeated shorter names,
overlapping names, Korean names, exact full-name precedence, repeated identical
packs and aliases of one asset. Each case also reuses the cache and validates
the resulting study request, including reference-price ownership and unaffected
remaining images and questions.

Before repair: 16 failed, 16 passed in 3.00 seconds. After repair: 181 focused
survey draft, reference, choice and API tests pass in 4.59 seconds. A final
alias-label stability adjustment passes all 32 new cases in 2.34 seconds.
Full-source Pyright reports zero errors and warnings. The main test run emits
61 existing LiteLLM logging coroutine warnings. No full suite, paid requests,
model weights or native inference were used.
