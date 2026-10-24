# Respect local-server capacity after concurrent endpoint changes

A structured request held its original endpoint's semaphore throughout optional
parameter and output-budget negotiation. If another request selected a fallback
while it was in flight, its internal retry used the new endpoint without acquiring
that endpoint's semaphore. Four concurrent customer requests could consequently
exceed a fallback server's limit of one or two, causing avoidable overload.

Async structured negotiation now acquires the current endpoint's semaphore when
its configuration differs from the one already protected by the outer request.
It checks the configuration again after acquiring a queued slot. Waiting through
another endpoint change sends no request and spends no negotiation attempt.
Original output-budget recovery bounds, endpoint-specific option learning and
cache identity rules remain intact. Context managers release both original and
replacement slots on success, failure or cancellation. The obsolete original slot
remains held until its request exits; queued original requests then recheck their
endpoint as before. Limits remain per client and event loop.

Before repair, 16 text/image cases exceeded the configured limit, reaching three
or four concurrent fallback requests; eight raw-text controls passed. The actual
OpenAI/LiteLLM/Instructor stack runs against mock HTTP, including a concurrent
authentication failure that selects the fallback. Cases cover old limits of four
or unlimited, new limits of one or two, shared model aliases, option and budget
rejections, retained new-endpoint parameters and absence of old-cache pollution.

After repair, 161 focused checks passed in 6.53 seconds. Additional coordinated
tests cover one or seven endpoint transitions while queued, unchanged request
counts, cancellation while waiting and during generation, and subsequent requests
using all released capacity. Related fallback, cache, usage and negotiation
checks also passed. Strict Pyright reported zero errors. Four existing LiteLLM
logging-cleanup warnings occurred. No live inference, model download or paid call
was used; this verifies request coordination, not real-server throughput.
