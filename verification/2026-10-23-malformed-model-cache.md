# Recover from malformed model-cache containers

The cache reader handled invalid JSON, missing result keys and invalid response schemas, but indexed
valid non-object JSON as a dictionary. Null, booleans, numbers, strings and arrays raised TypeError
before either synchronous or asynchronous generation reached the provider. Every retry hit the same
file, leaving the workflow blocked until the cache was manually removed.

Validate the entry container before reading its result. Invalid containers now follow the existing
unreadable-cache fallback, and a successful provider answer replaces the bad entry.

- New matrix: ten malformed entry shapes across synchronous/asynchronous public generation methods.
  Each case recovers through one offline provider double, caches the answer, and serves the next call
  from cache with correct request/token accounting.
- Before the fix: **12 failed, 8 passed in 1.97s**.
- New matrix, existing cache tests and the automatic-starter correction/cache regression:
  **28 passed in 1.92s**.
- Strict Pyright on `engine/llm_client.py`: **0 errors**.

No live model calls, full suite, frontend changes or release binary changes.
