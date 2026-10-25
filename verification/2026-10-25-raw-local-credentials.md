# Direct local model credential precedence

Named-provider credential isolation did not cover raw LiteLLM model references.
The default vision configuration uses `openai/local-vlm` with an explicit
loopback endpoint. If both `PARASTORE_LOCAL_API_KEY` and `OPENAI_API_KEY` were
set, its HTTP requests used the cloud key, causing a local server requiring its
own key to reject every request.

The client now prefers a nonblank local environment key for a loopback endpoint.
An explicit config credential still wins. A raw loopback gateway without an
explicit local key retains its existing OpenAI environment fallback; remote
gateway behavior is unchanged. Surrounding local-key whitespace is normalized,
as it already is for named providers. The existing loopback recognition is
shared with the structured-request retry limit, including IPv4 loopback ranges,
IPv6, localhost and its dotted spelling. Raw text keeps its existing retry policy.

Eighty scripted-HTTP cases use the real LiteLLM/Instructor stack across five
call modes. They cover address spellings, both environment keys, whitespace,
explicit credentials, absent/empty keys, remote/cloud/private-network endpoints,
and a localhost lookalike. Before the fix, 35 failed and 45 controls passed in
16.14 seconds. Requests are intercepted and only synthetic credentials are used.

All 273 focused credential, retry-budget, provider-option and fallback-chain
tests pass in 4.14 seconds. Full-source Pyright reports zero errors and warnings.
The test run emits 111 existing LiteLLM logging coroutine warnings. No paid
request, model download, native inference or full suite was used.
