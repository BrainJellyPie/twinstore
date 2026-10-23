# Ignore stale authentication decisions after a provider switch

Authentication recovery previously identified an in-flight request by model name alone. When two
endpoints exposed the same model name, one request could successfully switch to the second endpoint
while a delayed failure from the first endpoint still triggered another fallback decision and failed.
A slow fallback callback could also replace the newer endpoint with its stale choice, or propagate
its old failure even though another request had found a working configuration.

Recovery now compares the request's configuration identity before and after choosing a fallback.
An intervening switch reuses the current configuration. Callback errors still propagate when no
switch occurred, and the existing retry bound remains intact. This covers synchronous structured,
asynchronous structured and plain-text requests.

Focused offline evidence:

- Two simultaneous requests, with the second authentication failure released only after the first
  fallback succeeds: **3 failed, 3 passed in 2.11s** before repair. All three failures shared a model
  name across endpoints; different model names already worked.
- Delayed selection returning a stale candidate or raising after a newer switch:
  **3 failed, 3 passed in 2.26s** before the callback-error repair.
- Final endpoint, cache, key-fallback and parameter-retry tests: **58 passed in 3.31s**.
  Strict Pyright on the changed client module: **0 errors**.

All providers and selection callbacks are scripted. No model calls, full suite, frontend or release
changes; credentials and persisted provider settings are not changed by these tests.
