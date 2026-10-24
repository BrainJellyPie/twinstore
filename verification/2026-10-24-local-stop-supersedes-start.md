# A newer Stop supersedes a delayed local-model Start

An automatic start could read the old preference, pause, then clear cancellation
and launch a worker after the user had stopped the model. The Start endpoint had
the same gap between recording its choice and calling the manager. Persisting the
new Stop alone did not stop this older request from restarting the process.

Update the session choice under the manager's state lock. Under that same lock,
check for an explicit Stop before clearing cancellation, upgrading download
permission or creating the startup thread. A later explicit Start records a new
choice and proceeds normally. Automatic startup rechecks its final choice so it
does not report an upcoming model when a Stop superseded it.

Four deterministic regressions pause an automatic or button Start just before
worker creation, with either no prior choice or an existing Start. The Stop route
then records and performs the stop before the delayed call resumes. No startup
worker may run, cancellation must remain set, and a later button Start must work.
Before: all four scenarios incorrectly started a worker after Stop. After: 87
focused lifecycle, preference, provider-fallback and responsiveness checks passed
in 5.58 seconds. Strict Pyright reported zero errors in the changed module, and
`git diff --check` passed. No model process or download was started by these tests.
