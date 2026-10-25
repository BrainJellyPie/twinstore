# Reject contradictory positive and unmatched rival answers

The rival matcher rejected two different positive targets for one rival name,
but discarded an explicit unmatched answer before checking consistency. A reply
containing both a known target and an empty/null target therefore accepted the
positive match and could change the rival price index and venue adjustment.

An explicit unmatched answer now participates in consistency validation. A
positive target alongside that answer triggers the existing bounded Instructor
retry. Repeated contradictions fail without returning usable aliases. Duplicate
unmatched answers remain valid, and unknown names retain their existing ignored
behavior. The prompt explicitly forbids positive/unmatched contradictions.

The real LiteLLM/Instructor HTTP fixture covers JSON and JSON-schema modes,
both row orders, empty/null/whitespace unmatched values, a corrected second
answer, repeated failure, and an invalid cached entry. Thirty-six added cases
failed before the change; nineteen existing and duplicate-unmatched controls
passed. Accepted corrected matches still produce the expected price comparison
and are reused from cache without another HTTP request.

All 230 focused rival matching, comparison and venue-application checks pass in
6.05 seconds. Pyright on all source files reports zero errors and warnings.
The run emits 63 existing LiteLLM logging coroutine warnings. No paid inference,
model weights or full-suite run was used.
