# Parse final JSON after explicit thinking blocks

Structured parsing could consume JSON examples inside model reasoning. Leading
whitespace and consecutive `<think>` blocks could make a valid final object fail
JSON parsing; an unfinished block with `finish_reason=stop` could instead be
accepted and cached as the answer. The simpler single-block case was already
handled upstream, and output truncated with `finish_reason=length` already raised
the appropriate incomplete-output error.

Before Instructor validates each structured completion, a response hook removes
explicit leading thinking blocks. An unfinished block leaves no final answer and
therefore follows existing bounded validation recovery. It does not guess at
unmarked reasoning, alter tags inside JSON string values, or modify finish reasons
and token usage. Both synchronous and asynchronous text/image structured paths
use the hook. Raw text generation keeps its existing response semantics.

Structured cache identity now includes a parser version. Previously accepted
thought-only records lack the original response needed to identify them safely,
so old structured entries are bypassed and regenerated on first use. Files are
not deleted; subsequent requests reuse the new valid cache.

The corrected pre-fix regression run failed ten cases with 21 controls passing.
The final new test file has 33 passing cases, covering both JSON modes, four
structured call paths, whitespace and consecutive blocks, unfinished reasoning,
missing/invalid final answers, bounded retries, truncation, literal tags, cache
migration, raw-text preservation and usage. Focused client/retry/error/cache/slot
verification passed 205 tests in 5.62 seconds; strict Pyright reported zero errors.
There were 27 existing LiteLLM logging-cleanup warnings. HTTP transports and model
responses were scripted; no live model inference or reasoning-quality assessment
was performed. The managed server already requests reasoning off; this also
protects externally configured servers that expose explicit thinking blocks.
