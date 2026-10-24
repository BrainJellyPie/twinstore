# Classify truncated vision output by exception type

Entrance planning and shelf glances doubled their output budget whenever an
error string contained `max_tokens` or `length limit`. Instructor error strings
include generated answers and earlier failed attempts. Consequently a malformed
boolean/interest value containing those words, a rejected output parameter or an
HTTP 403 could all trigger a second, larger request. An earlier truncated attempt
also triggered recovery after a different terminal failure.

Both call sites now require an actual `IncompleteOutputException`, directly or
in the final failed attempt of an `InstructorRetryException`. The existing limit
of one doubled-budget retry remains. Other failures retain their existing
plan/glance error behavior, and provider parameter/output-budget negotiation
continues to belong to the shared client. Ensemble-vote behavior is unchanged.
The older plan regression fake now raises the actual typed truncation exception.

Before repair, twelve new cases failed and fifteen controls passed. Afterward,
174 focused checks passed in 44.93 seconds and strict Pyright reported zero
errors. They cover text/image entry plans and shelf glances through actual
OpenAI/LiteLLM/Instructor against mock HTTP: generated error-like strings, HTTP
400/403, one-off and persistent `finish_reason=length`, exact budget sequences,
direct/wrapped truncation and earlier versus terminal failed attempts. Existing
plan/glance behavior and provider-error/output-budget checks also passed. Eight
existing LiteLLM logging-cleanup warnings occurred. No live inference or paid
requests were used.
