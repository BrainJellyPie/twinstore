# Study startup, saved inputs and project deletion

Concept surveys, shelf comparisons, conjoint studies and staff-script tests could register work while
their project was being deleted. Both requests returned success; late job writes could recreate part
of a deleted project. A study starting during a customer/product save could also capture the old data.

All four starts now hold the project tree transaction through input capture and pending registration.
Shelf and staff-script tests additionally hold the source layout lock. Surveys and conjoint studies
have no source layout and do not wait on unrelated layout locks. Worker submission stays outside the
critical section; existing HTTP routes already use the thread pool. Busy starts return retryable 503s.

- Before the source fix: **20 failed, 10 passed in 4.25 s** in the corrected regression matrix.
- After the fix: **80 passed in 12.19 s**, covering the new races, contention and same-event-loop health
  checks, plus existing complete marketing/staff-script reports, currency, response-pair integrity,
  saved evidence, invalid requests and path validation.
- Strict Pyright on `application/marketing.py` and `application/staff_pitch.py`: **0 errors, 0 warnings**.
- `git diff --check`: clean.

Race tests use temporary projects and real locks. They test project deletion in both orders, accepted
customer and product saves, later customer edits preserving a registered panel, and relevant/unrelated
lock contention. Their panel double captures the selected inputs then deliberately fails before model
work; the existing API tests separately complete reports using fake models. No live model calls or
full-suite/frontend reruns were used.

```bash
# From backend/
.venv/bin/pytest -q tests/server/test_study_start_lifecycle.py tests/server/test_marketing_api.py tests/server/test_staff_pitch_api.py tests/server/test_survey_currency.py tests/server/test_shelf_test_integrity.py tests/server/test_marketing_setup_paths.py --tb=short
.venv/bin/pyright src/store_emulator/application/marketing.py src/store_emulator/application/staff_pitch.py
```

This closes startup races for these four study types. It does not change package-library mutation or
capture/lab-job lifecycles. It is a main-branch fix after v0.4.11; published release artifacts are unchanged.
