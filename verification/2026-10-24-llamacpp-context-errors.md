# Preserve llama.cpp context-overflow recovery through HTTP adapters

Following the typed context-error fix, the actual llama.cpp HTTP response revealed
another gap. Its HTTP 400 has `type: exceed_context_size_error`, with messages such
as `request (11897 tokens) exceeds the available context size (8192 tokens), try
increasing it`. The installed LiteLLM maps this to ordinary `BadRequestError`,
discards its response body, and Instructor wraps it. The typed-error recovery did
not recognize it.

Reference: [llama.cpp request checks](https://github.com/ggml-org/llama.cpp/blob/6b9ba4f2e8c1436511956f0b3c309e2c9e642071/tools/server/server-context.cpp#L3973)
and [error response formatting](https://github.com/ggml-org/llama.cpp/blob/6b9ba4f2e8c1436511956f0b3c309e2c9e642071/tools/server/server-common.cpp).

Recognize the two concrete llama.cpp token-count messages on a bad-request error:
the request exceeding available context and the input exceeding maximum context.
Apply the same check to Instructor's final recorded error. A typed
`ContextWindowExceededError` remains supported. Do not treat arbitrary mentions
of context, unsupported parameters or other bad requests as context overflow.

The offline integration test uses `httpx.MockTransport`, the real OpenAI SDK,
LiteLLM, Instructor and the selector. Both real-format context responses failed
before the change; the unrelated-error control passed. After the fix, all 114
focused recovery/API checks passed in 5.88 seconds, including both HTTP variants
and the negative control. Strict Pyright reported zero errors and
`git diff --check` passed. No live model requests or GPU inference were performed.
