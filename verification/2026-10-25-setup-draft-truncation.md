# Bounded setup-draft truncation recovery — 2026-10-25

Customer-profile drafts and automatic store forms retried a cut-off response at
the same 700/900-token limit until the request failed. They now use one additional
structured generation round at 1400/1800 tokens only when the terminal error is
Instructor's typed IncompleteOutputException. Original prompts, language, seed,
validation and the two-attempt limit per round are retained. Ordinary validation,
authorization and rate-limit errors do not trigger expansion; an earlier cutoff
followed by another failure does not trigger it either. Client defaults remain
unchanged and partial/invalid drafts cannot enter the response cache.

Validation:
- New 64-case harness initially had 32 failures and 32 passes in 3.21s.
- 167 focused tests passed in 5.50s: real OpenAI-compatible/native Ollama SDK
  transports with JSON and JSON-schema output, Korean draft preservation,
  terminal error ordering, store-format spelling, optional fields and assist API.
- Fixtures intercept HTTP; no model downloads or external inference.
- Full backend source Pyright: 0 errors, 0 warnings. Server boot passed.
- 45 existing LiteLLM async logging cleanup warnings; no test failures.
