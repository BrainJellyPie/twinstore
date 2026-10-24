# Recover a rejected local output ceiling

TwinStore's general generation ceiling is 65,535 tokens. vLLM deployments that
reject `input_tokens + max_tokens > max_model_len` can therefore reject even a
short automatic-generation request. The concrete error is present in
[vLLM v0.11.0 serving_engine.py](https://github.com/vllm-project/vllm/blob/v0.11.0/vllm/entrypoints/openai/serving_engine.py#L681).
Current upstream (`717cf843426ce85dbb7170aff7d7a833ad7d3c09`), in contrast, clamps
the ceiling in `entrypoints/serve/utils/api_utils.py::get_max_tokens`; no recovery
is needed for a server that already accepts the request.

The sync/async structured and raw-text clients now recognize this precise typed
HTTP 400 rejection, verify its reported ceiling matches the sent request, and
retry once with `context_length - input_tokens` when positive and smaller.
Configuration and global provider-option state do not store the adjusted limit.
Subsequent prompts start from their own ceiling; cache use stays consistent.
Existing optional-parameter negotiation retains its budget, including the
`max_completion_tokens` rename. Provider fallback starts from the next model's
settings. Concurrent provider changes discard stale limits without replenishing
the current call's retry allowance.

The check excludes generated-response validation text, mismatched token counts,
input overflow, nonpositive room, unrelated errors and non-400 HTTP responses.
A boundary test exposed LiteLLM translating a context-looking 403 into a 400
context exception: the original response/exception status now prevents that
misclassification from triggering recovery.

Seventeen initial HTTP recovery cases failed before the change. The final
verification covers 119 unique focused checks: 57 new budget/boundary cases and
62 existing option-isolation, malformed-output, cache-reroute and provider-chain
checks. The broad focused run passed 108 checks in 3.27 seconds; five additional
negotiation/Instructor checks passed in 2.31 seconds, followed by concurrent
provider-change controls and targeted final checks. The last 12 affected checks
passed in 2.43 seconds. Strict Pyright reported zero errors; diff whitespace
checks passed. Existing LiteLLM logging-worker coroutine cleanup warnings
appeared in some mixed sync/async runs (four in the broad run).

HTTP tests traverse OpenAI, LiteLLM and Instructor with deterministic mock
transports. They cover text/images, sync/async/raw modes, 8K/32K/128K contexts,
per-call overrides, cache hits, multi-attempt Instructor errors, parameter
renaming, repeated rejection, fallback and concurrent provider changes. No
weights, live inference or paid calls were used. This verifies protocol recovery,
not whether a particular model can finish its answer in the remaining space.
