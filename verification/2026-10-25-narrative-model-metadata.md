# Keep provider metadata out of generated A/B commentary

The A/B narrative response inherited the persisted report's `model` field.
That field was included in the model's schema even though the application
always replaces it with the actual answering provider. A local model returning
null, an object, a list, a number or a boolean there caused otherwise complete
commentary to fail both attempts.

Use a separate model response containing only summary, interpretation and
next steps, then convert it to the existing persisted narrative type. Extra
provider metadata in a reply is ignored. Summary validation and text limits
are retained, as are the two-attempt limit and legacy report compatibility.
The application still records its actual model reference, including reroutes.

Fourteen real LiteLLM/Instructor HTTP cases cover both JSON modes and omitted,
null, object, list, numeric, boolean and guessed-string metadata. Each must keep
all report text, use one request followed by a cache hit, and cache only generated
text. A schema check ensures the model is not asked to identify itself.

Before the fix all 15 checks failed in 3.41 seconds: ten malformed-metadata
cases failed inference, while the remaining five exposed the old schema/cache
metadata contract. The focused report, summary, API and lifecycle suite passed
86 tests in 9.59 seconds. Its API check also verifies the saved model reference
and rendered HTML/Markdown commentary. Full source Pyright reported zero errors
and warnings. The 29 warnings were existing LiteLLM async logging cleanup
warnings. No native inference, model downloads or paid requests ran.
