# Recover oversized customer input batches once

Customer generation already split a truncated output batch once, but a server
rejecting an oversized input caused the entire batch to fail. Small local
contexts could therefore fail the initial customer probe even when each half of
the requested batch would fit.

The same bounded split now handles a terminal, typed context rejection:
LiteLLM's `ContextWindowExceededError` or its `BadRequestError` carrying one of
llama.cpp's concrete input-token-count messages. The existing starter-selection
classifier is shared through the LLM client. It checks original HTTP statuses
before accepting LiteLLM's classification, because that library can relabel
context-looking HTTP 403/429 responses as context HTTP 400 errors. Those failures
must not cause either customer or starter decomposition. Generated text,
unrelated bad requests, timeouts and earlier failed Instructor attempts cannot
qualify a terminal failure for a split.

Each original batch still permits at most three structured calls (original plus
two sequential halves), each retaining the existing three Instructor attempts.
The shared semaphore is released before a child acquires it. IDs, original
arrival hours, logical progress and successful-child caching remain intact.
Children cannot split again. A failed child returns no partial original batch;
a single customer or shared prefix that still exceeds context remains a failure.
No profile, address or user instruction is truncated to force it to fit.

The initial new matrix had 29 failing cases and 11 passing controls. After repair,
145 focused customer-context, truncated-output, batch-grammar, starter-context and
output-budget checks passed in 4.34 seconds. Eight additional original-status and
cross-day semaphore cases passed in 2.31 seconds, for 153 unique checks. Coverage
includes 2/3/5/12 customers, direct/wrapped failures, last-attempt classification,
bounded persistent rejection, cache contents, both llama.cpp message forms,
OpenAI-style context messages, HTTP 400/403/429, and shared concurrency 1/2.
Mock HTTP exercises OpenAI, LiteLLM and Instructor translation together.

Strict Pyright for all three changed source modules reported zero errors. Two
existing LiteLLM asynchronous logging cleanup warnings occurred in the broad
focused run. No live inference, downloaded weights or paid calls were used.
