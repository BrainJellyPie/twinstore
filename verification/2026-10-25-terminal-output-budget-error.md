# Only the terminal output-ceiling error permits adaptation

Output-budget recovery searched every Instructor failure. A first vLLM-style
ceiling rejection followed by invalid output, truncation or an unrelated HTTP
400 therefore caused two more requests after the configured two attempts were
exhausted. Twelve real HTTP cases reproduced four calls instead of two across
sync/async text and image methods. Eight timeout/503 controls already stopped
correctly (2.34 seconds).

Recovery now examines the final attempt, requires its typed bad-request error
and matches the current request's output ceiling against that error's message.
The original HTTP-status checks remain. A genuine terminal ceiling rejection
still permits one request-local reduction; earlier errors cannot authorize it.

Regressions assert exact transmitted token ceilings/call counts and no cache
entry on failure. No live inference, network provider or paid call was used.

All 114 focused terminal-error, output-limit, usage and concurrent-fallback
checks passed in 4.03 seconds. Eight existing LiteLLM logging-cleanup warnings
occurred. Pyright reported zero errors/warnings; `git diff --check` passed.
