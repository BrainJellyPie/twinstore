# Optimization startup snapshot and project lifecycle

Optimization read its source layout, customers and operating settings without the saves' locks, then
registered its pending job separately. It could run on pre-save data or accept a job while its project
was being deleted. A paused pending write could recreate optimization records after project removal.

Startup now holds the project tree transaction and the source layout lock through input capture,
configuration validation and pending registration. Operating settings are resolved in that transaction,
with the existing request override/shared-store precedence. The worker is submitted after release.
The synchronous HTTP route already runs in the thread pool; lock waits return 503 on timeout.

Validation used temporary projects and real locks. New race tests intercept worker submission, while
the existing end-to-end API tests execute rule-based and fake-vision searches and apply their winners.
No live model requests were made.

- Before the fix: **8 failed, 9 passed in 3.32 s**.
- After the fix: **49 passed in 13.88 s**, including project deletion in either order, accepted layout/
  customer/operations saves, operations removal and precedence, contention, same-event-loop health,
  invalid numeric requests, source deletion, building metadata, cancellation and completed searches.
- Strict Pyright on the two changed source modules: **0 errors, 0 warnings**.
- `git diff --check`: clean. No frontend rebuild or full-suite rerun.

Commands (from `backend/`):

```bash
.venv/bin/pytest -q tests/server/test_optimization_start_snapshot.py tests/server/test_api_lock_responsiveness.py tests/server/test_optimization_input_numbers.py tests/server/test_optimization_apply_missing_source.py tests/server/test_optimization_apply_building.py tests/server/test_optimization_cancel_projects.py tests/server/test_optimize_api.py --tb=short
.venv/bin/pyright src/store_emulator/application/optimize.py src/store_emulator/server/routes/optimize.py
```

This covers optimization startup, not every other study or capture job. It is a main-branch fix after
v0.4.11; published release artifacts are unchanged.
