# Simulation concurrency must permit progress

`twinstore simulate --concurrency 0` and the A/B command accepted a zero
semaphore capacity. With customers present, the runner waited indefinitely;
with an empty population, the same invalid option silently completed. Negative
values failed only after input preparation and engine reset.

Validate the CLI option during argument parsing and reject nonpositive limits
at the beginning of the runner, before store preparation or engine calls.
Positive limits and their defaults remain unchanged.

## Evidence

- Before the fix: 12 new regression cases failed, while 2 valid-limit controls
  passed. A bounded offline call reproduced the zero-limit deadlock.
- After the fix: 62 focused tests passed in 4.33 seconds, covering zero and
  negative limits, empty/nonempty populations, both CLI commands, valid limits,
  opening hours, weekday congestion and reproducibility.
- `uv run pyright src/`: 0 errors, 0 warnings.
- All checks were offline; no model/provider requests were made.

Commands:

```sh
uv run pytest tests/engine/test_simulation_concurrency.py tests/engine/test_simulation_opening_hours.py tests/engine/test_simulation_weekday_congestion.py tests/engine/test_reproducibility.py -q --tb=short
uv run pyright src/
```
