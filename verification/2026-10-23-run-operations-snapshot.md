# Run operating settings captured with the layout

The simulation route read a layout's saved operations before acquiring the lock used to capture its
store and customers. If an operations save was in progress, the run waited for that save and then
started using the old operating settings. A saved change from five shelf units to 33, or removal of
the saved settings, could therefore be ignored by the run that followed it.

`prepare_simulation` now resolves operations while holding its existing layout lock and returns the
resolved settings with the other inputs. The route passes that captured value to the worker. Internal
callers were updated for the additional return value; the HTTP response remains unchanged. Explicit
operations, forced sharing and shared-store opt-out retain the existing selection rules.

Validation used temporary projects, actual locks and controlled concurrent saves. The new race matrix
intercepts worker submission and inspects the exact operating settings the worker receives. Related
integration checks also run offline rule-based previews and inspect their saved configurations.

- Before the fix: **8 failed, 12 passed in 4.48 s**.
- After the fix: **92 passed in 15.56 s**. Coverage includes both save/start orders, updates/removal,
  final/preview runs, inherited/default/explicit/disabled operations, run ID reservations, editor state,
  API responsiveness, resource ID validation, currency consistency and vision shelf-view keys.
- Strict Pyright on the two changed source modules: **0 errors, 0 warnings**.
- `git diff --check`: clean. No model calls, frontend rebuild or full-suite rerun.

Commands (from `backend/`):

```bash
.venv/bin/pytest -q tests/server/test_run_operations_snapshot.py tests/server/test_simulation_setup_races.py tests/server/test_run_id_reservation.py tests/server/test_api_lock_responsiveness.py tests/server/test_resource_id_validation.py tests/server/test_store_currency.py tests/server/test_shelf_views_api.py::test_keys_match_the_store_a_vision_run_uses tests/server/test_layout_operations.py::test_runs_use_the_layouts_operations_unless_told_otherwise --tb=short
.venv/bin/pyright src/store_emulator/application/simulation.py src/store_emulator/server/routes/simulate.py
```

This change covers simulation starts. It does not claim identical snapshot coordination for separate
marketing or optimization job starts. It is a main-branch fix after v0.4.11; release archives are unchanged.
