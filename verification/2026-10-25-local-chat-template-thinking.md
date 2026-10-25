# Direct answers from named template-capable local servers

TwinStore starts its managed llama.cpp server with reasoning disabled, but calls
to named external llama.cpp/vLLM providers did not carry the corresponding
request control. Qwen3 can therefore spend a short JSON answer budget reasoning
and finish with `length` before producing any answer. Increasing an output cap
after that failure does not turn its template reasoning off.

Named vLLM and llama.cpp configurations now resolve a runtime template policy.
The client sends `chat_template_kwargs.enable_thinking=false` through the real
OpenAI-compatible SDK path for text and image calls. It includes that policy in
cache identity, and resolving another named provider clears it. Generic custom
gateways, raw references, Ollama and cloud provider controls are unchanged. This
does not guarantee non-thinking behavior for models whose templates cannot
disable reasoning; it uses the control these two server protocols provide.

Protocol evidence:

- [Pinned vLLM reasoning documentation](https://github.com/vllm-project/vllm/blob/717cf843426ce85dbb7170aff7d7a833ad7d3c09/docs/features/reasoning_outputs.md)
  documents Qwen3's default and the request template switch.
- [Qwen3-8B tokenizer configuration](https://huggingface.co/Qwen/Qwen3-8B/blob/b968826d9c46dd6066d109eabc6255188de91218/tokenizer_config.json)
  was rendered locally with the client's actual template arguments. Before this
  change its assistant prefix had no forced empty thinking block; afterward it
  exactly matched the template's explicit disabled mode. Only the 9,732-byte
  tokenizer configuration was fetched, with no weights or model execution.
- The inspected llama.cpp server documentation also accepts
  `chat_template_kwargs` with `enable_thinking=false`.

Thirty-five new cases cover both provider types, family IDs and a served alias,
five call modes, other-provider isolation and old-policy cache exclusion. The
scripted HTTP server returns a truncated reasoning-only response unless it
receives the documented switch. Before the fix 31 cases failed and four controls
passed in 3.88 seconds. These fixtures verify request behavior, not native model
failure rates. The Qwen3.5 cases exercise an explicitly enabled server/template,
not a claim that every size of that family enables thinking by default.

All 288 focused template, parser, cache, credential, slot and fallback tests pass
in 5.92 seconds. Full-source Pyright reports zero errors and warnings. The test
run emits 120 existing LiteLLM logging coroutine warnings. No full suite, paid
request, native inference or model accuracy/latency measurement was performed.
