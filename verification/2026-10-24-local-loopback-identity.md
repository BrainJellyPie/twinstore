# Do not infer server identity from a loopback port

The endpoint-readiness fix initially treated `127.0.0.1`, `localhost` and `::1`
as one server when the port and path matched. That is unsafe for readiness:
IPv4 and IPv6 sockets can listen independently on the same port, and localhost
resolution may choose either address. The execution environment confirmed this
with simultaneous IPv4-only and IPv6-only listeners bound to one ephemeral port;
both sockets were then closed.

Trust the manager's lifecycle state only when the configured hostname also
matches. Probe other hosts at their actual configured address, whether the
managed server is ready, starting or failed. A trailing slash on the identical
host/path still identifies the known endpoint. This change affects assistive
fallback and model listing; it does not assert that host aliases are different
models, only that manager state alone cannot prove their readiness.

Expanded endpoint regressions now treat localhost and IPv6 loopback as independent
servers across seven manager states and both health outcomes. Twenty checks failed
before the refinement and 62 controls passed. After: 143 focused endpoint,
provider readiness, fallback and API responsiveness checks passed in 3.52 seconds.
Strict Pyright reported zero errors; `git diff --check` passed. Health responses
were mocked; no model inference or downloads were used.
