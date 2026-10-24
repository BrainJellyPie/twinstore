# Send dotted-localhost model requests directly

The launcher exempted localhost, IPv4 loopback and IPv6 loopback from proxies,
but omitted `localhost.`. Direct readiness probes could succeed while OpenAI SDK
model requests went to a configured proxy and failed with HTTP 403. Both sync
and async requests reproduced this with lowercase and uppercase hostnames.

Add the fully qualified localhost spelling to the launcher's existing bypass
list. Preserve the user's proxy configuration and other bypass entries. This
runs before starting the backend, so the SDK receives the corrected environment.

Before the fix, the four real-SDK HTTP cases failed with proxy permission errors;
the three existing configuration controls passed in 0.79 seconds. Tests start a
local model-protocol fixture and a rejecting local proxy, then assert that one
completion reaches the model and zero requests reach the proxy. No model runs.

The focused launcher, estimates and readiness run passed 136 checks; two async
cases encountered this environment's dotted-host DNS timeout. Pinning only that
test hostname's DNS result to loopback made the fixture deterministic without
changing HTTP hosts, proxy selection or production code. The final proxy suite
passed all seven checks in 0.59 seconds: 138 distinct relevant checks now pass.
Full source Pyright reported zero errors and warnings. No native inference,
model downloads or paid requests were used.
