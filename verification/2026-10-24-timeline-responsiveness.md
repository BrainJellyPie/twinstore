# Keep playback loading off the request loop

The timeline endpoint read and decoded its complete result file synchronously
inside an async handler. FastAPI then encoded the response on the same event
loop, so other HTTP requests waited behind a slow read or serialization.

The synchronous handler now runs on FastAPI's worker pool and returns an already
encoded Response. A Pydantic object adapter uses the same JSON semantics as the
previous unconstrained response field, including legacy nonfinite values becoming
null. Reading and serialization both occur in the worker; the endpoint does not
add a second parse or an intermediate JSON object conversion.

Controlled read and serializer delays each prevented an unrelated health request
from completing before the change. Both now leave health available while playback
continues waiting. The first serializer probe targeted JSONResponse.render, which
the installed FastAPI does not use for this response field; it was corrected to
the actual TypeAdapter.dump_json path before confirming the serialization failure.

29 focused checks passed in 3.81 seconds, including a real offline shared-store
run, result totals, path validation, UTF-8, exact large integers, nulls, empty and
missing results, legacy nonfinite values and named damaged-file errors. Strict
Pyright identified an inferred empty-list type; making it explicit cleared the
type check, and the missing-result case passed again. No live model calls or full
suite rerun occurred. The test isolates event-loop dispatch, not a guarantee of
latency under CPU saturation or exhausted worker capacity.

```sh
uv run pytest -q tests/server/test_timeline_responsiveness.py tests/server/test_resource_id_validation.py tests/server/test_shared_store_api.py::test_a_shared_store_run_reports_its_stock_and_tills --tb=short
uv run pyright src/store_emulator/server/routes/simulate.py
```
