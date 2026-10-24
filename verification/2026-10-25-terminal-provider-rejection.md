# Final-attempt provider classification

Authentication and optional-parameter classification searched earlier failures
even after Instructor ended with invalid output, truncation or a timeout.
Scripted real HTTP sequences reproduced all 24 combinations of those terminal
failures, the two earlier rejection kinds and sync/async text/image calls in
2.82 seconds. Authentication cases invoked the provider-switch callback and
returned the backup answer; parameter cases learned an obsolete rejection and
made extra calls. In the application the switch callback also rejects the key.

Instructor wrappers now expose only their final attempt for classification.
Generated validation content stays excluded. Ordinary exception causes and
cycle protection remain, and wrappers without an attempt record still expose
their cause. This keeps terminal authentication/parameter recovery while
preventing a different terminal error from changing provider configuration.

The new HTTP regressions assert no switch callback, no learned sampling-option
rejection, the exact two-call budget and no successful cache entry. All calls
use mock transports; no live credentials, native inference or paid APIs are used.

All 157 focused terminal-classification, key-fallback, provider-option and
output-budget checks passed in 5.27 seconds. Seventeen existing LiteLLM
logging-cleanup warnings occurred. Pyright reported zero errors/warnings;
`git diff --check` passed.
