# Reject web pages mistaken for a ready local model

Readiness accepted any HTTP 200 from `/health`, without reading its body. A local
web app with an HTML catch-all route therefore passed preflight for both text
and vision runs even though it provided no inference API.

Inspect the health body. Preserve vLLM's empty success, plain OK/healthy replies
and recognized JSON status markers, including llama.cpp's busy-slot status.
Unrecognized bodies proceed to the existing OpenAI model-list and Ollama tag
probes. Existing authentication handling and authoritative non-success HTTP
statuses remain unchanged. This is an availability check, not an inference or
model-quality test.

The expanded protocol reproduction failed 14 checks while 46 controls passed
in 1.91 seconds. It covers HTML, plain unknown-route text, unrelated JSON,
error objects and wrong status types, both with and without a real model list.
Two tests start a small local HTTP server whose catch-all returns HTML with 200;
they verify availability and text/vision preflight, including successful fallback
when that same server also exposes an actual model list. No model is loaded.

The focused protocol, provider, endpoint-identity and engine-availability tests
passed all 299 checks in 4.75 seconds. Full source Pyright reported zero errors
and warnings. No native inference, downloads or paid requests were used.
