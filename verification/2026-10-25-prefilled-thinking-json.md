# Keep prompt-prefilled reasoning out of final answers

The existing cleaner recognized only responses beginning with `<think>`.
Some reasoning models receive that opening token in the prompt and emit only
the closing token. When an endpoint forwards this text without separating
reasoning, JSON examples in the thoughts can corrupt the final response or be
accepted even when no final answer exists.

This format is supported by vLLM's
[base thinking parser](https://github.com/vllm-project/vllm/blob/v0.11.0/vllm/reasoning/basic_parsers.py),
which explicitly handles models that may not generate the start token, and by
its [DeepSeek R1 parser](https://github.com/vllm-project/vllm/blob/v0.11.0/vllm/reasoning/deepseek_r1_reasoning_parser.py).
This finding does not assert that every model or server returns this format.

The shared final-answer cleaner now accepts a leading closing tag or a closing
tag on its own line, including whitespace and CRLF. It keeps only the content
after that boundary and still handles subsequent explicit thinking blocks.
Inline literal markers and escaped newlines in JSON strings remain untouched.
Unmarked reasoning cannot be identified reliably and is not guessed away.

Structured response parsing and supplemental CSV/XLSX summaries both use the
cleaner. Raw text completion continues returning the provider's raw content.
The structured-parser cache identity advances to `final-think-v2`, so previously
cached reasoning examples cannot bypass the corrected parser. Existing cache
files are retained, but old structured answers are regenerated on their next use.

Before the fix, 20 protocol cases failed and 21 controls passed in 3.66 seconds.
The failing cases included accepting a fenced reasoning example when the final
answer was absent. The final suite covers both JSON modes, sync/async text and
image calls, missing/invalid finals, truncation, literal markers, old-cache
isolation, summary length limits and downstream customer evidence. Scripted
HTTP replies traverse the real LiteLLM/Instructor parser; no native model ran.

All 289 focused checks passed in 6.59 seconds. Full source Pyright reported zero
errors and warnings. The 47 warnings were existing LiteLLM async logging cleanup
warnings. No model weights were downloaded and no paid requests ran.
