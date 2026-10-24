# Responsive model settings

The `/api/models` handler performed synchronous local-model health requests on
the server event loop. An unresponsive enabled local model therefore paused all
unrelated HTTP requests until its health timeout. The provider update handler
also waited for the shared settings lock on that loop. The provider list moved
its health checks to a worker, but evaluated its synchronous settings read before
entering the worker.

The three synchronous provider handlers now use FastAPI's standard worker-thread
dispatch. This covers settings reads, model discovery, lock waits and persistence,
including the existing response validation and HTTP error behavior.

Four regressions failed before the change: slow local discovery returning either
available or unavailable, delayed provider-list settings reads and a save blocked
on the real shared settings lock. An unrelated `/api/health` request could not
complete until the original operation was released. The tests use controlled
events and the real provider service; no model or external network calls occur.

After the change, 36 focused checks passed in 3.68 seconds, including local
readiness, malformed saved addresses and endpoint option isolation. Strict
Pyright on the changed route module reports zero errors. The blocked request
still waits for its own operation, then returns the correct model list or saved
settings; unknown providers still return 404.

```sh
uv run pytest -q tests/server/test_provider_api_responsiveness.py tests/server/test_provider_local_check.py tests/engine/test_provider_local_readiness.py tests/engine/test_provider_option_isolation.py --tb=short
uv run pyright src/store_emulator/server/routes/providers.py
```
