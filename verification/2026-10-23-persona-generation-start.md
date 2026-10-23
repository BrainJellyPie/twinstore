# Customer generation registration

Starting customer generation checked the project's history, running layouts and other generators without
protecting the interval before writing its pending status. Concurrent run starts, customer edits, duplicate
generation requests and deletion could all be accepted in that interval. This could queue duplicate model
work or later replace the population used by a final simulation.

Generation now holds the existing project layout transaction through validation, retained-upload handling
and pending registration. The worker is submitted after releasing the locks. The regeneration route waits
in the thread pool, keeping status and health requests available while another operation holds a lock.

Preserved behavior: a preview that already captured its inputs permits later regeneration. A pending
generation blocks new previews. Once registered, generation uses project metadata and can finish after
its source layout is deleted; deleting the whole project still requires the generation to finish.

Validation used real file locks and controlled overlapping requests against temporary projects. Workers
were intercepted at submission, so no model calls were made.

- The pre-fix reproduction exposed conflicting run/generation acceptance in either order, duplicate job
  submission across the same or different layouts, deletion races and accepted customer edits during startup.
- Final regression matrix: **19 passed in 6.51 s**, including final/preview runs, both request orders,
  same/different layouts, deletion, customer edits and tree/layout/unrelated-lock boundaries.
- **115 related tests passed** in the broader focused run (persona lifecycle and missing projects, API
  responsiveness, metadata/customer/run races, wizard templates and provider fallback). That initial run
  also passed 18 of the new cases; the remaining assertion incorrectly forbade later source-layout deletion.
  Its expectation was corrected to preserve the behavior above, then all 19 new cases were rerun.
- Strict Pyright on both changed source modules: **0 errors, 0 warnings**.
- `git diff --check`: clean. Backend-only change; no frontend or full-suite rerun.

Commands (from `backend/`):

```bash
.venv/bin/pytest -q tests/server/test_persona_generation_start_races.py tests/server/test_persona_generation_missing_project.py tests/server/test_persona_lifecycle.py tests/server/test_api_lock_responsiveness.py tests/server/test_project_metadata_races.py tests/server/test_persona_save_run_races.py tests/server/test_project_start_deletion_races.py tests/server/test_project_templates.py tests/engine/test_key_fallback.py --tb=short
.venv/bin/pytest -q tests/server/test_persona_generation_start_races.py --tb=short
.venv/bin/pyright src/store_emulator/application/generation_async.py src/store_emulator/server/routes/setups.py
```

This is a main-branch fix after v0.4.11; published archives and the release tag are unchanged.
