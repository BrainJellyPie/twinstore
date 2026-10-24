# Recover incomplete marketing study registration

Survey startup wrote pending status before saving its stimulus image. Staff-script
startup did the same before saving the product and respondent inputs. A failure
in either later save returned an error without submitting work, leaving a pending
job that blocked deletion indefinitely. Request/status save failures also left
incomplete directories across all five marketing study kinds.

Registration now exclusively creates its job directory and removes that directory
if its request or status cannot be saved. Survey image and staff-script input
failures perform the same cleanup while still holding the startup tree guard.
An occupied destination returns 409 before writing or removing any previous files.
The 12-character job ID format is unchanged.

Evidence:

- 17 regression cases failed before the fix: request/status replacement failures
  for five kinds, a partial survey image, staff-script inputs, and occupied
  directories for each kind.
- 97 focused checks passed in 17.09 seconds, covering registration recovery,
  successful retries, preserved history, worker admission/status failure handling,
  image snapshots and startup lifecycle guards.
- Strict Pyright on both changed application modules: zero errors.
- No live model calls, frontend changes or full-suite rerun.

Commands:

```sh
uv run pytest -q tests/server/test_study_registration_persistence.py tests/server/test_study_queue_failure.py tests/server/test_worker_status_persistence.py tests/server/test_marketing_image_snapshot.py tests/server/test_study_start_lifecycle.py --tb=short
uv run pyright src/store_emulator/application/marketing.py src/store_emulator/application/staff_pitch.py
```

The checks inject handled write failures, including a partial image. They do not
claim crash atomicity or recovery when directory cleanup itself cannot complete.
Previously stranded jobs are not migrated; existing restart recovery still applies.
This changes main after v0.4.11 and does not replace the published release archives.
