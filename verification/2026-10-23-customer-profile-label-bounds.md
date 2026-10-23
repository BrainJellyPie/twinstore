# Align trade-area labels with generated customers

The trade-area schema accepted customer types and visit purposes longer than 120 characters, while
the customer prompt required those exact labels and its response schema rejected them. A valid first
response could therefore make every subsequent customer batch fail.

Use one bounded string type for both schemas. Invalid labels now enter the existing structured-response
retry during trade-area analysis; they are not silently truncated or renamed.

Focused cases cover identity/purpose labels at 119, 120 and 121 characters in Latin, Korean, Chinese
and emoji, plus complete offline generations that correct the initial answer before requesting batches.
Before the fix, the new cases produced **16 failed, 16 passed in 0.29s**. Afterward, these cases plus
traffic boundaries, missing weekdays, generation choices and two existing schema/prompt checks produced
**86 passed in 3.27s**. Strict Pyright on the changed module reported **0 errors**.

The previous check output was unavailable after context recovery, so the focused checks were repeated
once to retain observable results. No live model calls, full suite, frontend or release binary changes.
