# Keep automatic staff-script alternatives usable

An automatic draft could return the current script unchanged and cache that
response as successful. The subsequent A/B request rejected equal scripts, and
drafting again returned the same unusable cached answer. Capitalization and
whitespace changes caused the same failure.

Validate alternatives against the supplied current script inside the model
response schema, before caching. The prompt now describes this requirement, and
the existing two-attempt limit requests correction. An empty current script still
allows a first draft; optional explanations and genuinely different wording keep
their existing behavior. The comparison uses the A/B request's whitespace and
case normalization.

The new reproduction initially failed 18 cases while four controls passed in
2.91 seconds. Both JSON modes exercise the real LiteLLM/Instructor/OpenAI HTTP
path with scripted responses: exact copies, case changes, Unicode whitespace,
successful correction, repeated failure, old invalid cache entries, later
recovery and cache reuse. Valid alternatives also construct a complete A/B
request. Korean alternatives and blank-current drafts remain accepted.

The focused script-draft, optional-annotation, staff-pitch and API tests passed
all 95 checks in 4.57 seconds. Full source Pyright reported zero errors and
warnings. The 17 warnings came from LiteLLM's existing async logging cleanup.
No native model, model downloads or paid requests were used.
