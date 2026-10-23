# Project metadata saves and deletion

Concurrent metadata updates read the same old JSON and replaced each other's accepted changes. A customer
save's timestamp update or generation's summary, traffic profile, or visitor estimate could undo a user's
new name/address/profile; the user's edit could erase the generated evidence. A pending edit could also
recreate metadata after the project and all its layouts had been deleted.

Metadata read-modify-write operations now use the existing project tree transaction. Customer saves and
project deletion already hold that transaction. Generation holds it only while reading and saving metadata,
not during model work. Existence is rechecked after acquiring the lock. The metadata route waits in the
thread pool and preserves 404/503 application errors. Unrelated projects and layout-only locks do not block
metadata edits.

Validation used temporary projects, actual file locks, controlled overlapping writes, and fake generation
dependencies. No model calls were made.

- Before the fix: `test_project_metadata_races.py` — **12 failed, 4 passed in 3.99 s**.
- After the fix: **103 passed in 10.73 s**, covering metadata overlaps in both orders, deletion in both
  orders, contention and missing-project boundaries, same-event-loop health responsiveness, customer/run
  races, project lifecycle, persona neighborhood input and provider fallback behavior.
- Strict Pyright on the three changed source modules: **0 errors, 0 warnings**.
- `git diff --check`: clean. Backend-only change; frontend and full suites were not repeated.

Commands (from `backend/`):

```bash
.venv/bin/pytest -q tests/server/test_project_metadata_races.py tests/server/test_api_lock_responsiveness.py tests/server/test_persona_save_run_races.py tests/server/test_project_start_deletion_races.py tests/server/test_project_deletion_lifecycle.py tests/server/test_personas_project_existence.py tests/server/test_persona_neighborhood.py tests/engine/test_key_fallback.py --tb=short
.venv/bin/pyright src/store_emulator/application/projects.py src/store_emulator/application/generation_async.py src/store_emulator/server/routes/projects.py
```

This fixes metadata writes; it does not claim atomic startup for every background job. It is a main-branch
fix after v0.4.11 and does not change that release's tag or downloadable archives.
