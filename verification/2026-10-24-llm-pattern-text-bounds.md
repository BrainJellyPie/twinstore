# Prevent optional pattern prose from overflowing the next request

The first LLM simulation stage accepted unlimited reasoning and optional
`grammar_override` text. The latter was inserted verbatim into stage two, so a
small model repeating an optional rule could turn an otherwise usable selection
into an oversized next request.

The response grammar now bounds reasoning to 600 characters and optional rule
rewrites to 1,200. Existing built-in pattern grammars are at most 228 characters;
the rewrite limit leaves room for substantial short customization. Providers
ignoring those grammar constraints retain the first 600 reasoning characters,
but an oversized rewrite is discarded whole: the engine uses the complete
selected pattern instead of executing a partially cut rule. Normal rewrites and
custom pattern IDs remain unchanged. Prompts describe the short-answer limits.

An offline Qwen3.5 tokenizer probe measured stage-two user text at 15,158 tokens
for a repeated English rewrite and 16,659 for a Korean one; both become 245 tokens
with the default selected grammar. These are synthetic response-boundary probes,
not measurements of live model frequency or a guarantee that every store catalog
fits a given model's context.

Before repair, 23 cases failed and twelve controls passed. The focused non-HTTP
run passed 111 checks in 0.55 seconds. After correcting the separately published
strict-coordinate regression, all 37 new cases passed in 2.36 seconds, including
two complete three-stage HTTP/cache tests: 113 unique checks in total. Cases cover
both route orderings, English/Korean/CJK/emoji strings, exact length boundaries,
preserved short rewrites, default-rule handoff, actual purchases/exits, transmitted
JSON-schema bounds, JSON mode and cache reuse with no extra model requests.

Changed-module strict Pyright reported zero errors. All model responses were
scripted; HTTP used a mock transport through OpenAI, LiteLLM and Instructor. No
live inference, downloaded weights or paid calls were used.
