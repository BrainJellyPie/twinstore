# Keep the chosen shopper behavior and its purchase limits

The behavior-selection grammar listed valid IDs, but non-enforcing model
responses were accepted as arbitrary strings. Known variants such as padded
`WINDOW_SHOPPING` then missed the exact lookup and silently selected the first
pattern. In the HTTP reproduction, a window shopper bought two product lines
for 500 cents instead of buying nothing; a quick-snack shopper kept both lines
instead of its one-product limit.

The request-specific pattern schema now uses the existing identifier resolver
to recover unique case and surrounding-space variants of the supplied IDs.
It retains exact custom IDs, does not choose between case-distinct ambiguous
IDs, and preserves existing unknown/missing-ID fallback. Raw wrong types still
fail. The prompt explicitly asks for unchanged capitalization and separators.
The shared domain pattern model and custom grammar text are unchanged.

The new HTTP matrix covers all 12 built-in patterns in JSON and JSON-schema,
both route orderings, and padded uppercase IDs. It checks complete checkout
spend and line count, product-limit drops, the selected downstream grammar,
trace identity, unchanged narrative text, cache reuse, exit and source-store
immutability. Custom-ID collision, unknown-ID and wrong-type controls extend
the existing grammar and concurrent request isolation tests.

Before the repair, 50 tests failed and 27 passed in 5.11 seconds. The focused
pattern, text-bound, offline-engine, required-intent and optional-impulse suites
then passed 189 checks in 9.57 seconds. A type-check correction copied the
enum list into its JSON-typed context without changing its contents; its 12
HTTP grammar cases passed again in 2.40 seconds. Full source Pyright then
reported zero errors and warnings. These are scripted provider responses
through real parsing/routing/checkout, not native model inference or measured
model error rates. No model downloads or paid calls were used.
