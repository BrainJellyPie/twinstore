# Preserve saved commentary when a model returns a blank summary

Study commentary and A/B narratives accepted empty or whitespace-only summary
strings. These replies were cached as successful answers and could overwrite
an existing saved review. A rewrite using the same request then reused the
empty result without another model request.

Require a nonblank, trimmed summary in the model-only schemas and state that
requirement in both prompts. Study commentary retains two attempts; A/B
narratives now also allow two attempts so the model can correct the missing
content. The saved `StudyReading` and `ReportNarrative` formats remain compatible
with old empty records. Additional explanation and next-step strings may still
be empty when a nonblank summary was returned.

The 24 application/HTTP cases cover both JSON modes and both commentary paths,
empty and Unicode-whitespace summaries, corrected replies, exhausted retries
and invalid cached replies. They exercise the real LiteLLM/Instructor stack,
actual reading/narrative files and cache reuse. Persistent invalid replies must
return 502 and leave the existing file byte-for-byte unchanged. A compatibility
control loads old empty readings and narratives.

Before the fix, 24 checks failed and the legacy-reading control passed in
2.75 seconds. The focused commentary, report, theme, API and lifecycle suite
passed 92 tests in 7.42 seconds. Full source Pyright reported zero errors and
warnings. The 27 warnings were existing LiteLLM async logging cleanup warnings.
No native inference, model downloads or paid requests ran.
