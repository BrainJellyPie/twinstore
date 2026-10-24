# Retain individual needs in impulse decisions

The impulse prompt included cohort, age, gender, behavior, visit-purpose label,
category preferences and budget, but omitted the individual's description and
purchase intent. Needs such as a preference for decaf or an unsweetened drink
therefore disappeared when not repeated in the coarse labels or action narration.
Changing only these fields also reused the previous impulse answer from cache,
even though the pattern and intent stages received the changed shopper.

Nonempty description and intent now reach the impulse prompt verbatim and become
part of its cache identity. No additional model call is needed for an ordinary
visit. Empty values add no empty prompt rows.

Six HTTP cases reproduced both missing context and stale cache reuse across JSON
and JSON-schema modes, changing description, intent or both while holding other
inputs and the planned route constant. The corrected pipeline makes three fresh
stage requests per distinct shopper context and reuses all three for an identical
repeat. Related basket facts, exact offers, compact exposure and budget prompts
also pass: 126 tests in 5.83 seconds. Strict Pyright: zero errors. All responses
were scripted; live model adherence to personal preferences was not measured.
