# Recover after an adopted local server disappears

TwinStore can adopt a vision-capable llama.cpp process already listening on its
default port. Unlike a managed child, this server has no process handle to poll.
Its ready state previously persisted after the server exited or stopped serving
models. The setup screen disabled Start, and even a direct Start API request
returned the stale ready state without running the startup pipeline.

Setup refresh and Start now explicitly check an adopted endpoint. An unavailable
server becomes an error state, allowing the existing Start action to recover.
Ordinary internal status reads and managed-process status checks do not acquire
this network cost. The external probe runs outside the manager lock; its result
cannot overwrite a state transition that occurred while it was waiting.

The new tests use a real loopback HTTP server with health and vision props,
exercise actual adoption, and then close the socket, return 503, or replace the
API with an HTML application. They cover recovery through setup refresh and a
direct Start request, healthy reuse, managed status without HTTP checks, and a
delayed probe alongside health/status requests and newer state transitions.
Replacement inference startup is stubbed; no model weights or paid calls run.

Before the fix, nine checks failed and two controls passed. The focused local
model, cancellation, preference, protocol and API responsiveness selection now
passes all 130 tests in 5.48 seconds. Full-source Pyright reports zero errors and
warnings. The full suite and native-model startup were not run.
