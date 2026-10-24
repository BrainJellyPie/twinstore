# Isolate invalid model endpoints from the engine selector

A malformed configured or saved server URL could raise while determining vision
defaults or model readiness, failing the whole `/api/engines` response. A missing
host could instead appear available, and an inline API key skipped endpoint
readiness entirely. Users could lose access to otherwise valid engines or be
offered a model that could not accept requests.

Validate basic HTTP(S) endpoint structure, hostname presence and the port before
availability checks. Invalid endpoints do not trigger local probes or managed
vision fallback. Mark only the affected engine unavailable and reject execution
before preparation with an actionable address error. Resolve and check explicit
endpoints even when a key is supplied; retain direct cloud-key availability.

The initial API reproduction failed all 24 cases in 3.40 seconds. Adding inline
credentials after the initial repair exposed 14 failures among 48 cases in
3.74 seconds. Coverage includes malformed IPv6 forms, nonnumeric ports, missing
hosts, text/vision engines, direct settings/provider references and keys present
or absent. Assertions preserve the other working engine and rule preview,
prevent invalid probes and check preflight rejection.

The focused provider, readiness, fallback and API suite passed 333 tests in
4.70 seconds. One additional API control passed in 3.04 seconds, retaining both
cloud engines with inline credentials and checking that the key is not returned
in the response (334 distinct passing checks). Full source Pyright reported zero
errors and warnings. No native inference or paid model calls were used.
