# Customer-generation confirmations commit atomically

Confirmation previously wrote `choice.json` before updating `status.json`. If
the second write failed, the request raised an error but the worker still read
the first file and accepted the choice. A failed "all" or "sample" confirmation
could therefore start customer-writing calls while the UI still offered retry.

The accepted choice now lives in progress alongside the closed confirmation
window, committed by the existing atomic status writer under the choice lock.
Workers consume only a choice from a running job's saved progress. A failed
write preserves the original confirmation, and an orphaned legacy choice file
cannot start work. Normal worker progress replaces the accepted choice after
handoff. Existing overlap and timeout locking is preserved.

Three new regression cases failed before the fix, covering all/sample/cancel
with a failed status save. The focused checks also exercise actual fsync and
file-replacement failures, every original/retry choice combination, an orphaned
legacy file, overlapping confirmations, delayed saves crossing the deadline,
and successful generation/cancellation handoff. The cancellation integration
test now answers the actual confirmation rather than staging an answer before
the worker asks.

Validation: 77 focused tests passed in 8.73 seconds; strict Pyright reported zero
errors or warnings. No live model calls. The generation API already accepts
arbitrary progress fields; existing customer counts remain unchanged.

This guarantees the saved choice and progress agree. A transport failure after
a successful commit does not undo that committed choice; reloading status shows
the accepted job, and duplicate answers remain rejected.

```sh
uv run pytest tests/server/test_generation_choice_persistence.py tests/server/test_generation_choice_handoff.py tests/engine/test_write_choice.py tests/engine/test_generation_provider_estimates.py -q
uv run pyright src/
```
