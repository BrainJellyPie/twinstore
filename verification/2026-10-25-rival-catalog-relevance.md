# Keep relevant references in bounded rival comparisons

Rival matching supplied the first 300 store product names in shelf order. At
301 products, a relevant last product was absent from the model's input even
when its brand and variant words were more specific than every earlier name.
The resulting unmatched answer omitted that product from price comparison and
the suggested attraction factor.

Each request now uses the existing prompt relevance selector with the current
rival batch as its query. The 300-reference limit remains in place, including
after capacity recovery splits a batch. Word overlap only selects candidates
for the prompt: it does not confirm product identity or create an alias.

New real LiteLLM/Instructor HTTP cases cover 299, 300 and 301 products, the
target at either end, English and Korean names, and both structured modes.
The scripted responder copies a known match only when that reference appears
in its input. Correct matches reach price and pull-factor calculations and
cached reuse without changing the store or capture. Existing different-variant,
ambiguous-name, bounded-prefix, conflict and adaptive-batch tests remain valid.

Before repair: 4 failed, 20 passed in 2.71 seconds. After repair: 253 focused
tests pass in 11.52 seconds. Full-source Pyright reports zero errors and
warnings. Tests emit 135 existing LiteLLM logging coroutine warnings. No full
suite, paid calls, weights or native inference were used. These tests establish
input coverage and recovery behavior, not a real model's matching accuracy.
