# Generated customer narratives

The generated-customer schema accepted empty and whitespace-only `description`
and `intent` strings. These responses became normal customers and cache entries,
so repeated generation reused customers without their individual context or
visit intent. A scripted HTTP probe through LiteLLM and Instructor reproduced
the issue in both JSON modes; each second run reused the invalid customer.

Only the model-generation schema now strips surrounding whitespace and requires
at least one character in both narratives. The prompt explicitly requires real
content and permits browsing without a purchase. Existing manual/stored Persona
models and optional preference/behavior defaults remain unchanged. The existing
three-attempt generation budget handles invalid responses before cache writes;
old cache entries are also revalidated.

The new regression matrix covers both JSON modes, both required fields, empty
strings, ASCII and Unicode whitespace, correction, repeated failure and invalid
cached responses. It verifies customer count, arrival day/hour, retained optional
defaults, bounded attempts and later reuse of corrected content. Short negative
and Unicode narrative controls remain valid.

Before repair: 37 failed and 2 passed in 3.74 seconds (36 pipeline cases plus one
whitespace-normalization control failed). After repair: 220 focused customer
narrative, vocabulary, optional-field, batch-grammar, budget and capacity-recovery
tests passed in 7.84 seconds, with one existing LiteLLM logging coroutine warning.
Full-source Pyright reported zero errors and warnings. These checks used scripted
HTTP responses, not paid requests or native model inference.

An additional 24 mixed-batch cases put one blank field in the first, middle or
last of five customers, across both JSON modes and correction/exhaustion paths.
All 24 failed against the unchanged release source in 3.11 seconds. The complete
new regression file then passed all 63 cases in 4.10 seconds against the repair,
preserving five distinct IDs and the original 09:00/23:00 arrival allocation.
Exhausted invalid batches leave no partial cache. This brings the distinct
focused checks passed across the final runs to 244; application source did not
change after the clean type check.

This change was prepared in an isolated worktree while v0.4.14 CI ran; it is a
post-release change and is not included in the v0.4.14 tag.
