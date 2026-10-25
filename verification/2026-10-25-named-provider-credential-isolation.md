# Isolate credentials when a named local provider has no key

Named llama.cpp, vLLM and custom providers resolved their own configured key,
but left it unset when none was configured. The OpenAI-compatible client then
inherited OPENAI_API_KEY or, for a custom endpoint, PARASTORE_LOCAL_API_KEY.
Thus selecting a no-key server could send another provider's credential and
receive an authentication failure instead of using that server as configured.

Named local providers using the OpenAI SDK now resolve an explicit not-needed
placeholder when their own key is absent. Saved and provider-specific environment
keys still take precedence. The placeholder is neither saved to settings nor
reported as a configured user key; serialized run configuration still excludes
the api_key field. Raw LiteLLM configuration behavior is unchanged.

Scripted HTTP checks actual Authorization headers for all three named providers,
with and without the OpenAI/local environment keys, across synchronous and
asynchronous text/image structured calls and raw text completion. Wrong headers
receive 401 without contacting any external server. Before the change, 25 cases
failed and 35 controls passed. The initial assertion-based fixture run was stopped
because its synthetic exceptions triggered SDK connection backoff; the final
reproduction uses the explicit 401 response instead.

The focused provider, readiness, credential and API responsiveness run passes
140 checks in 4.03 seconds. Three custom-key precedence controls and two existing
provider resolution/serialization checks also pass (145 distinct checks total).
Full-source Pyright reports zero errors and warnings. The main run emits 60
existing LiteLLM logging/event-loop warnings. All keys are offline test strings;
no real credential, paid inference or full-suite run was used.
