# Correct invalid automatic shelf-test targets before caching

The shelf-test designer previously cached a syntactically valid model draft
before resolving its product against the current layout. A nonexistent or
ambiguous product then failed conversion outside Instructor, so trying again
could repeatedly retrieve the same unusable cached draft.

A request-local draft validator now runs the existing target conversion inside
Instructor's existing two-attempt budget. A bad target gets one correction with
the concrete missing/ambiguous-product error. Repeated failures are not cached,
and a later retry can obtain a fresh answer. The prompt asks for a uniquely
identifiable listed product without inventing or guessing a target. Valid drafts
still resolve against the current layout and do not mutate it.

The existing review workflow is retained: missing packages, unusable optional
prices and drafts with no changes remain reviewable with their warnings. These
are not promoted into new hard failures.

Before: twelve correction/cache checks failed, while four partial-draft controls
passed. After: 67 focused draft, product-resolution, price-boundary and API checks
passed in 3.95 seconds. Cases include blank/whitespace names, invented names,
misleading substrings, Korean names, duplicate names across SKUs, immediate
correction, repeated failure followed by a later retry, cache reuse and source
immutability. Strict Pyright reported zero errors; diff whitespace checks passed.

The new correction/cache tests traverse OpenAI, LiteLLM and Instructor using
mocked HTTP responses. No weights, live inference or paid calls were used. This
verifies target validity and recovery, not whether a model chooses a useful study.
