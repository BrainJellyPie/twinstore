# Optional commentary detail recovery — 2026-10-25

Both study readings and A/B narratives accepted empty interpretation/next-step
strings but rejected null or missing versions of the same optional details.
A local model's otherwise valid summary was discarded after repeated validation
failures. The internal response schemas now normalize only null optional text to
empty strings and supply defaults for omitted details. Prompts explicitly request
empty strings when no supported detail can be given. Required summaries still
must be nonblank strings; numbers, booleans, lists and objects remain invalid text.
Public response fields and cached/saved content stay ordinary nonnullable strings.

Validation: baseline 32 failed, 36 passed in 6.12s. After the change, 97 focused
tests passed in 4.19s: intercepted OpenAI-compatible/native Ollama SDKs, both JSON
modes, either/both null details, omission, empty strings, strict summary/type
checks, cache reuse, model metadata, large report context and persistence for all
five study kinds. Full backend Pyright: 0 errors, 0 warnings; server boot passed.
There were 57 existing LiteLLM async logging cleanup warnings; no live inference.
