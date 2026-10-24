# Align integration tests with the current release behavior

The first v0.4.12 CI run stopped because an old capture-deletion test created a
capture without its parent project's metadata. The project lifecycle guard
correctly returned 404 before reaching the running-job guard that test intended
to exercise. The fixture now creates a project.

One complete local backend audit then collected the remaining integration issues:
32,203 passed, 26 failed, and one optional detector check skipped in 1117.02 seconds.
All failures came from four old test modules:

- A substitution test expected an unknown height when an alternative appeared at
  several levels. Current replay chooses a physical offer and records its level.
  The test now verifies the selected level and calibration distribution, while
  preserving the assertion that the input shopper remains unchanged.
- Twenty neighborhood cases expected a zero basket effect when one entire arm
  failed. Current analysis rejects unavailable evidence. These cases now require
  that error; partial-failure and valid-pair metric checks remain in place.
- Four restart-recovery cases and one saved-layout validation case omitted the
  parent project. Their fixtures now create metadata so they reach their intended
  deletion and unsafe-path guards.

After the test-only corrections, all 168 checks in the five affected modules
passed in 10.39 seconds. No application code changed. The local full suite was
not repeated; the release workflow runs its existing checks before publication.

```sh
uv run pytest -q --maxfail=30 --tb=short
uv run pytest -q tests/engine/test_audit_round2.py tests/engine/test_impulse_placement_profile.py tests/engine/test_synergy_incomplete_pairs.py tests/server/test_background_job_recovery.py tests/server/test_synergy_setup_validation.py --tb=short
```
