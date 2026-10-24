# Separate generated response failures from provider rejections

Instructor's retry-exception string includes rejected model completions and
validation input values. The client searched that whole string for authentication
and unsupported-option markers. A malformed or truncated model answer containing
`invalid api key; temperature is not supported` therefore disabled temperature,
made an extra request and invoked the authentication fallback callback even
though every HTTP response was successful. Application fallback can then mark
the current provider's working key as rejected for the session.

Traverse actual exceptions inside Instructor wrappers and ordinary cause/context
chains, excluding response-validation, JSON-decoding and incomplete-output errors.
Authentication checks and option-learning use this same traversal. Generated
completions are never inspected for provider capability or key failures. A visited
set keeps cyclic exception chains finite; actual wrapped provider rejections
continue to work.

Eight HTTP regressions cross sync/async text and image requests with complete but
invalid answers or length-truncated answers. Real OpenAI transport, LiteLLM and
Instructor must surface the response failure after the requested single attempt,
without changing learned options, invoking fallback or caching output. Twelve
additional cases cover validation/JSON/truncation errors and temperature, token
limit, thinking and reasoning markers. Controls check the base Instructor wrapper,
real unsupported-parameter exceptions, cause chains and cycles.

Before: all 20 initial regressions failed. After: 97 focused error-classification,
option-isolation, retry-boundary, key-fallback and cache checks passed in 3.48
seconds. Three warnings came from LiteLLM's asynchronous logging cleanup while
the transport tests repeatedly opened and closed event loops. Strict Pyright
reported zero errors; `git diff --check` passed. No live inference or real keys
were used.
