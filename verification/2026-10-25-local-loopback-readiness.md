# Keep loopback model addresses local through preflight and estimates

`localhost.` was treated as a cloud endpoint by customer-writing estimates and
batch selection. With an unbounded configured request limit, a measured
20-minute local write was estimated as one minute, bypassing the sample/all
choice and using the larger cloud batch size. Readiness checks also used a
three-host allowlist, skipping probes for dotted localhost, other 127/8
addresses and expanded IPv6 loopback. An unavailable server could therefore
pass preflight and enter repeated failures or vision fallback during a run.

Recognize the fully qualified localhost spelling in the existing local-address
helper and use that helper in both readiness entry points. Keep exact endpoint
comparison for the managed server's startup state; independent servers retain
their own readiness and do not inherit managed startup or cloud routing.
Private-network and remote hostnames retain their existing provider policy.

Before the estimate fix, 15 new cases failed and 29 passed in 2.59 seconds.
Before the readiness fix, 48 new cases failed and 35 passed in 2.05 seconds.
Tests cover mixed hostname casing, HTTP/HTTPS, alternate IPv4 and IPv6 loopback,
working and unavailable independent endpoints, managed off/starting/disabled
states, text and vision run configurations, and nonlocal hostname controls.
Assertions include the 20-minute estimate, sample-selection handoff, local
batch size, exact probed address and refusal before model work starts.

The final focused suite passed 334 tests in 4.66 seconds, covering generation
estimates, run/ensemble/history estimates, provider status and startup isolation.
Full source Pyright reported zero errors and warnings. No model inference or
model downloads were used.
