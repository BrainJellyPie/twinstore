# Avoid repeated readiness waits when listing engines

The engine list checked readiness for each engine and again while calculating
its suggestion. When text and vision models shared one server, the same endpoint
was checked four times in one API request. Every slow or timed-out check added
another wait, and repeated observations could disagree within a single response.

Keep endpoint readiness results only within the current engine-list call.
Models sharing the exact endpoint reuse one result; different hosts, ports and
paths remain independent. Nothing persists across API requests, so a server
starting or stopping is reflected on the next request.

Before the fix, all four new API cases failed in 2.95 seconds; the shared endpoint
received four probes instead of one. Tests exercise identical endpoints and
different host/port/path values, then repeat each request through unavailable,
available and unavailable states. They verify actual probe counts, both model
engines' readiness and uninterrupted rule-preview availability.

After the fix, 180 focused engine availability, invalid-address, provider
responsiveness, endpoint identity and local-protocol checks passed in 4.01 seconds.
Full source Pyright reported zero errors and warnings. No native inference,
model downloads or paid model calls were used.
