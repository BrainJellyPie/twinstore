# Actionable advice for terminal model failures

Failure messages previously searched the entire Instructor exception string,
including earlier attempts and model-generated completion/validation content.
A final timeout, malformed answer or cutoff could therefore tell a user to
replace a working API key. Native Ollama's SDK additionally wraps HTTP errors
as APIConnectionError, so a running server's 400, 401, 403, 404, 429 or 5xx
response misleadingly suggested that the model could not be reached.

Advice now unwraps the last Instructor attempt, with cycle protection, and
recognizes typed validation/JSON/cutoff failures before inspecting diagnostic
text. Explicit context overflow uses the existing strict classifier. For the
known native Ollama adapter wrapper, the immediate original HTTP response
selects advice for rejected requests, credentials, access, missing model or
endpoint, rate limits, or server/resource failure. Actual connection failures
retain connection advice. Operational retries, key rejection and model
selection are unchanged; this repair concerns the user-facing explanation.

Twenty-three new cases failed before repair in 2.31 seconds. Eight run through
real native HTTP, LiteLLM and Instructor; the others build real typed parsing,
validation and retry exceptions with conflicting earlier-attempt/model text.
The final focused run passes 115 cases in 4.72 seconds, including existing
server feature checks and rejection-learning boundaries. Full-source Pyright
reports zero errors and warnings. Tests emit 18 existing LiteLLM logging
coroutine warnings. No full suite, model weights, native inference or paid
requests were used.
