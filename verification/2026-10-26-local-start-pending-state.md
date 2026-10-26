# A scheduled local-model start is already preparing

2026-10-26, based on main `faba583d`. When the cloud environment reconnected,
the saved model files and diagnostics remained, but both old llama-server
processes were defunct. Restarting the actual 2B CPU supervisor returned
`off` immediately after `start(wait=False)`. The scratch supervisor treated
that as terminal and exited before the startup worker could proceed.

The same state window exists in the application: `LocalVLMManager.start`
created a background worker under its lock, but only that worker set the
state to `preparing`. An immediate status read or Start API response could
therefore retain the previous `off` or `error` state. The settings UI treats
those as unavailable and polls them every 60 seconds, versus 2 seconds for
preparation. The provider fallback already had limited workarounds for this
window; the state transition itself was still late.

An accepted new start now sets preparation, its message and an empty progress
value while holding the manager lock, before starting the worker. Existing
ready or busy starts still reuse their current work. Explicit Stop continues
to supersede Start, and the worker checks cancellation before touching
hardware or downloading anything.

Five deterministic regressions pause the worker before it can set any state.
Before the fix, direct and HTTP starts from both off and error return the
stale state; preparation cancellation also fails its pending-state check.
The corrected pre-fix suite has five failures without warnings. An earlier
fixture lacked cancellation in failure cleanup and emitted one thread warning;
that fixture cleanup was corrected before application changes.

After the fix, 129 affected backend tests pass in 3.78 s. They cover the new
API/pending cases, repeated starts, startup/stop races, cancellation, stored
choice, disappeared external servers and assistive local endpoints. Strict
Pyright reports zero errors/warnings and the backend import smoke passes.
No frontend files change and no full suite is run.

A fresh manager then adopted the actual running CPU VLM at port 8082. Its
immediate status was `preparing`, followed by `ready`, with `managed=false`.
This is a real service lifecycle check with zero model inference calls, not
a second download or fresh model load. Its artifact is
`/workspace/scratch/cpu-vlm-probe-2b/start-status-after/result.json`.

The scratch supervisor was separately repaired to tolerate an off state while
its manager is busy, which allowed testing before the application fix. The
accompanying CPU prompt report records actual 0.8B/2B behavior and withheld
experiments; the startup fix makes no change to model-generated decisions.
