# Validate only the rival products requested in the current batch

Capacity recovery divides rival matching into smaller requests. Results already
discarded rows belonging to other batches, but the earlier model validator
checked those rows for contradictions first. A small model that repeated two
inconsistent answers for an earlier product caused the whole comparison to fail,
even when every answer for the current batch was correct.

Each batch now validates a response model that filters unrequested rival names
before checking contradictions and caching. The prompt explicitly limits output
to the current request. Current-batch conflicts still use the existing correction
attempt and terminal failure behavior; matching rules and batch limits are unchanged.

The existing real LiteLLM/Instructor recovery matrix now covers both conflicting
positive repetitions and a positive/unmatched repetition for an earlier product,
alongside its original single-extra-row controls. Both JSON modes, context/length
failures, capacities 1/3/8 and cached reuse retain every requested product and
the learned smaller batch size. An 81-row control verifies that conflicting
answers beyond the 80-row request cap are ignored. Existing active-product
conflict, identity and bounded-name regressions remain included.

Before repair: 24 failed, 12 passed in 7.34 seconds. After repair: 206 focused
matching, recovery, identity and conflict tests pass in 8.07 seconds. Full-source
Pyright reports zero errors and warnings. Tests emit 63 existing LiteLLM logging
coroutine warnings. No full suite, paid calls, model weights or native inference
were used.
