# A/B experiment input snapshot and daily traffic scale

Experiment startup read its layout, customers and operating settings outside the locks used by saves,
then registered pending work separately. It could use pre-save inputs or recreate study files after
project deletion. The worker also read daily visitor estimates when finishing: an experiment begun
with 100 visitors/day could be reported using 900 after a concurrent metadata change.

Startup now holds the project tree transaction and source layout lock through input capture and pending
registration. It captures both observed and simulated daily traffic with the population, so subsequent
metadata edits do not change the study's financial scale. Worker submission happens after lock release.
Lock timeouts return 503, and the existing thread-pool route leaves unrelated API requests responsive.

- Before the fix: **10 failed, 1 passed in 3.54 s** in the new regression matrix.
- After the fix: **63 passed in 9.36 s** across the new snapshot tests and related API, population,
  opening-hours, variant names, layout operations, currency and responsiveness tests.
- Strict Pyright on `application/marketing.py`: **0 errors, 0 warnings**.
- `git diff --check`: clean.

Tests use temporary projects, real locks and fake evaluators or the rule engine. They cover deletion
in both orders; accepted layout/customer/operations changes and removal; visitor estimates changed or
removed after start; contention; and control/variant consistency. No live model calls, full suite or
frontend rebuild was needed. The validation output from an earlier invocation was unavailable after
context recovery, so the focused checks above were rerun after confirming no check was still running.

Commands (from `backend/`):

```bash
.venv/bin/pytest -q tests/server/test_experiment_start_snapshot.py tests/server/test_api_lock_responsiveness.py tests/server/test_experiment_shoppers.py tests/server/test_experiment_population.py tests/server/test_experiment_variant_names.py tests/server/test_marketing_setup_paths.py tests/server/test_marketing_api.py::test_rule_ab_test tests/server/test_layout_operations.py::test_an_ab_test_on_the_layout_shares_its_store tests/server/test_store_currency.py::test_currency_mismatch_starts_no_run_or_experiment --tb=short
.venv/bin/pyright src/store_emulator/application/marketing.py
```

This change covers A/B experiment startup, not the other study types. It is a main-branch fix after
v0.4.11; published release artifacts remain unchanged.
