# Recover rival matching within a smaller local context

A larger output ceiling cannot make a combined request and answer fit an 8,192
token slot. A tokenizer-only fixture with 300 Korean reference labels and 80
rival names measured 7,167 input-content tokens plus 4,252 answer tokens. Forty
pairs still measured 8,579 combined tokens; twenty measured 7,159. These counts
cover prompt/schema content and the example answer, not a native chat template.

The matcher now halves a failed batch after a terminal typed input-context
rejection or IncompleteOutputException. It retries the same rows and keeps the
smaller size for subsequent rows. Successful replies retain normal request-cache
reuse. Authentication, forbidden responses, unrelated bad requests, malformed
JSON and contradictory matches do not trigger decomposition. A one-row failure
propagates; it cannot retry forever. The existing 80-rival and 300-reference caps
are unchanged, and an oversized reference catalog can still fail at one row.

Replies can only contribute aliases for the current requested batch. A copied
name from an earlier task cannot overwrite that earlier result. This also stops
accepting a known name beyond the existing 80-row prompt cap when it was never
asked about. Full-name ambiguity and contradiction validation remain in place.

Scripted HTTP uses real LiteLLM and Instructor in both output modes, with capacities
of one, three and eight rows. It verifies all nine source rows survive uneven
splits, the smaller size is retained, max_parallel=1 does not deadlock, and valid
subtasks are cached. Failure controls include a truncation followed by a terminal
authentication error, ensuring only the final attempt controls recovery.

Before the change, 13 of the initial 25 checks failed and 12 controls passed.
Four single-row exhaustion controls were then added. All 323 focused rival/API
checks pass in 8.51 seconds; full-source Pyright reports zero errors and warnings.
There are 123 existing LiteLLM logging coroutine warnings. No full suite, paid
inference or native model execution was used.
