# Resolve rival names without losing exact identities

Rival labels previously required a byte-for-byte copy while our product names
were collapsed into a case-folded dictionary. A model's harmless case or outer
whitespace change could discard a valid rival alias. Conversely, different
Unicode names such as Maße and Masse collapsed to one dictionary key, so the
last listed product replaced the model's exact target and its comparison price.

Both lists now retain their original distinct names. Exact copies take priority;
case/outer-whitespace variations resolve only to a single known candidate.
Ambiguous names remain unmatched. The existing 160-character prefix guard still
considers every possible full name before accepting a bounded answer. Canonical
rival labels also feed the contradiction check, so a spelling variation cannot
hide an incompatible positive and unmatched answer for the same product.

The new fixture drives real LiteLLM and Instructor through scripted HTTP in JSON
and JSON-schema modes. It checks both list orders, exact Unicode targets,
ambiguous folded targets, copied labels with casing/whitespace, unknown names,
case-colliding rival labels, comparison prices, cache reuse and immutable source
objects. Four additional checks cover contradictions across copied-label forms.
Before the fix, 24 checks failed and 16 controls passed.

All 270 focused rival matching, bounded-name, comparison and venue-application
checks pass in 6.68 seconds. Full-source Pyright reports zero errors and warnings.
The run emits 99 existing LiteLLM logging coroutine warnings. No paid model call,
model-weight execution or full-suite run was performed.
