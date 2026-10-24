# Require primary candidate selection during context recovery

When a large primary shopping prompt exceeded local context capacity, an empty
or explanation-only candidate-selection reply became a successful empty list.
The focused planner then received no candidate products, and that omission could
be cached as if the shopper had explicitly selected nothing.

Require the codes field only for primary-plan recovery and state that requirement
in its prompt. Missing fields now use the existing two-attempt correction budget
and fail before focused planning if still invalid. Explicit empty selections are
valid. Optional impulse selection keeps its existing default so it cannot discard
an otherwise complete planned visit. Code membership, bounds and deduplication
are unchanged.

Before the fix, 12 cases failed and eight controls passed in 3.55 seconds.
Scripted HTTP covers both JSON modes and route orderings, repeated omissions,
bounded correction, invalid legacy cache entries, subsequent recovery, explicit
empty choices and omitted optional impulse choices. Execution checks preserve
the exact planned SKU, two units, 200 in revenue, one checkout and exit.

The focused selection, context-recovery and LLM-engine suite passed 153 checks
in 11.95 seconds. After replacing unpacked Field keyword arguments with an
explicit bound for strict typing, all 21 new checks passed again in 3.80 seconds
and full source Pyright reported zero errors and warnings. No native model
inference was used.
