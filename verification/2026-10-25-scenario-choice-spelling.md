# Recover known choices in model-written scenarios

The scenario writer rejected `Rain`, `WEEKEND`, `Sports_Match` and `Discount`,
including otherwise valid values with surrounding spaces. A non-enforcing
local provider could repeat these recognizable choices through Instructor's
correction attempts and fail the entire situation draft before any effects
or shelf changes could be reviewed.

Only model-facing fields now canonicalize known case and surrounding-space
variants: weather, season, day type, crowding, music, lighting, event kind and
promotion kind. They reuse the existing unique-identifier matcher before
enum/literal validation. The prompt asks for exact schema spellings and
underscores. Product targets, stock-out identifiers, annotations, prices,
weekdays and defaults retain their existing semantics. Unknown synonyms,
internal spacing changes such as `1 + 1`, wrong types and nonoptional nulls
are still rejected; an unspecified null season remains valid. Domain models
and manually authored scenario contracts are unchanged.

Eighty-six scripted HTTP cases exercise every one of the 43 supported choices
in both LiteLLM/Instructor structured modes, with uppercase letters, ideographic
leading whitespace and trailing tabs. Each complete scenario, compiled
effects and applied store is compared against its canonical equivalent.
The checks preserve Friday-only restrictions, stock-outs, source-store data
and cache reuse with just one successful request. Further controls reject
unknown strings, numeric/boolean/container types and invalid nulls, preserve
annotations and targets exactly, and verify that a repeated unlisted choice
still fails after two attempts without creating a cache entry. Three API
cases compare complete canonical responses against uppercase, title case and
whitespace variants across all choice fields together.

The pre-fix new-test run failed 87 checks and passed 72 in 12.12 seconds.
After the fix, the focused scenario and API suite passed 355 checks in 8.09
seconds. It reported 193 instances of the known LiteLLM logging-cleanup warning
(`Logging.async_success_handler` was never awaited), with no request failures.
Full source Pyright reported zero errors and warnings. Tests used scripted
responses and real scenario compilation/application; no native model
inference, weights or paid calls were used. These cases demonstrate handling
of spelling variants, not their frequency in real model output.
