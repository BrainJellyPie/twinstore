# Generated traffic counts match the customer population

The model traffic schema accepted duplicate hours and negative visitor counts. Later stages summed
all rows for daily estimates but keyed generation by hour, silently replacing repeated hours.

Offline full-pipeline reproductions:

- Hour 9 returned twice with 10 and 20 visitors: saved estimate **30**, generated customers **20**.
- Hour 9 had 20 visitors and hour 10 had -10: saved estimate **10**, generated customers **20**.

Hourly values now require integer hours 0–23 and non-negative integer counts. Daily responses validate
that each hour appears at most once. These validations run inside the response model used by the
existing three-attempt structured generation request. Invalid estimates cannot reach persona writing
or populate daily estimates; no duplicate rows are guessed, merged or silently discarded.

- Before the fix: **10 failed, 15 passed in 0.30 s** in the new matrix.
- After the fix: **35 passed in 3.17 s**, including invalid-response cases, generated/shuffled valid
  profiles, 24-hour and one-hour windows at midnight/end-of-day, closed-hour filtering, small written
  samples with copied visitors, population cap, confirmation flow and existing fallback behavior.
- Strict Pyright on `engine/generators/persona.py`: **0 errors, 0 warnings**.
- `git diff --check`: clean. No paid/live model calls or full-suite/frontend reruns.

```bash
# From backend/
.venv/bin/pytest -q tests/engine/test_generated_traffic_boundaries.py tests/engine/test_write_choice.py tests/engine/test_key_fallback.py::test_an_open_day_never_ends_up_without_customers tests/engine/test_key_fallback.py::test_a_long_list_of_identities_still_fits_each_hour tests/engine/test_key_fallback.py::test_generated_customers_carry_only_what_the_prompt_asks_for tests/engine/test_key_fallback.py::test_a_day_is_filled_to_its_estimated_visitors_with_twins_of_the_written_customers --tb=short
.venv/bin/pyright src/store_emulator/engine/generators/persona.py
```

Tests use an offline model double. They verify rejection before writing and valid population/estimate
agreement, not the likelihood that a particular live model corrects an invalid response. Existing saved
customers/estimates are not migrated. This is a main-branch fix after v0.4.11; published binaries are unchanged.
