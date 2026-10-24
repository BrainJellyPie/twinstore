# Keep model visits working in layouts without counters

Layouts without counters are supported with a payment-unavailable warning. The
engine already omitted its own automatic checkout in these layouts, but accepted
a model-supplied pay action after a valid planned buy. The provisional route then
raised No reachable checkout, failing the entire customer before impulse handling.

The engine now removes pay from executable planned actions when no counters exist,
before constructing the route. The original model response remains in the trace.
The intent prompt explicitly permits omitting pay in this case. Existing purchases,
budget rules, exit behavior and counter-present payment routing are unchanged.

The pre-fix test reproduced the failure with both planned and nearest ordering;
32 controls passed. Expanded HTTP tests cover both structured modes, absent/present
counters, missing/ordinary/out-of-grid payment hints, duplicated early and late
payments, exact offer decoding, quantities, checkout timing and cached reuse.
Related impulse-only/no-purchase cases, malformed visit frames, unreachable offers
and context recovery pass too: 227 tests in 6.42 seconds. Strict Pyright reports
zero errors. Responses were scripted; no live inference was used.
