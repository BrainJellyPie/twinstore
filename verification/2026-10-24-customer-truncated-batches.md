# Recover truncated automatic customer batches

A local model that could write two or three customers but ran out of output room
when asked for five previously retried the same five-customer request, then lost
the whole batch. When this happened during the initial probe, generation stopped
before the user could choose a sample or a full population.

After the existing Instructor attempts are exhausted, a typed incomplete-output
failure now permits one split into two contiguous smaller requests. Only the
last recorded failure in an Instructor wrapper qualifies. Child requests cannot
split again, use the existing three-attempt setting, and acquire the shared
semaphore after the parent's slot has been released. Thus there are at most three
structured requests for an original batch (up to nine Instructor attempts),
without increasing peak concurrency. One-customer batches cannot be split.

Each returned customer is paired with its original requested hour before child
results are combined. This also handles a short nonempty child response without
shifting later customers into earlier hours. Existing ID assignment, progress,
logical-batch failure accounting, short-response population filling, and
source/customer persistence safeguards remain unchanged. If either child fails,
the parent batch fails without returning a partial recovered group. Only complete
child responses enter the LLM cache; a repeated original request can still incur
its initial cutoff attempts before using cached children.

Before: 14 new failures, five controls passed. After: 88 focused generation,
concurrency, missing-day, generated-ID and budget checks passed in 3.07 seconds.
Five additional shared-semaphore, last-failure and HTTP/cache checks passed in
2.12 seconds, for 93 unique checks. Cases include 1/2/3/5/10/12 customers, odd
splits, direct/wrapped truncation, repeated child failure, short child responses,
mixed visit hours, successful probe handoff, two open days and exact HTTP request
counts. Strict Pyright and diff whitespace checks passed. The HTTP run emitted
the existing LiteLLM logging-worker coroutine cleanup warning at test teardown.

The HTTP test uses real OpenAI/LiteLLM/Instructor processing with a mock transport
returning `finish_reason=length`. No weights, live inference or paid calls were
used. This verifies bounded recovery and preserved scheduling, not whether every
physical model can finish even the smaller requests.
