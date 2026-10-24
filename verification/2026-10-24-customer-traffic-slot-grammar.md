# Assign traffic clocks in the harness

The traffic grammar allowed repeated hours and empty lists. Repeated clocks
failed semantic validation on all three attempts, aborting customer generation.
An empty list was accepted and invoked the existing generic-day fallback instead
of retaining a model-estimated distribution. Sixteen scripted HTTP cases
reproduced these outcomes in JSON and JSON-schema modes, for a one-hour midnight
window, the last hour of the day, ordinary daytime opening and a full 24 hours.

The model now returns count/type rows in the explicitly listed opening-slot
order. The harness supplies each hour; the transmitted grammar omits clock IDs,
forbids extra row fields and fixes the number of rows to the number of open slots.
Zero-visitor slots still occupy their place. A partial positional list cannot
shift later estimates into earlier hours: wrong lengths and mixed labelled /
unlabelled rows receive corrective validation errors.

Explicit-hour responses from non-enforcing or older providers remain supported,
including sparse and unordered rows; duplicate hours, invalid counts and clock
bounds retain their validation. Closed-hour visitors are still zeroed. Cached
results contain assigned clocks and validate identically on reread. The existing
fallback for a non-enforcing empty or all-zero estimate remains unchanged.

An initial inline schema reused a label reference from a separate Pydantic
definition registry. Focused tests caught that construction error; the final
schema inlines the original label constraint and has no unresolved references.
It does not repeat a complete schema per hour: Qwen tokenization of the indented
JSON schema measures 247 tokens for 1/9 slots and 249 for 24 slots. The system
prompt measures 387–389 tokens, excluding user evidence, chat framing and output.

The final focused coverage contains 266 distinct tests. This includes 28 HTTP
cases for generation, corrections and cache separation, schema validation of
numeric/label bounds, positional length guards, legacy explicit clocks, changed
opening windows, large counts, shared labels, truncation recovery, concurrency,
sample probes, missing days and customer identifiers. Runs passed 81 tests in
3.91 seconds and 209 in 5.85 seconds (24 overlapping). Strict Pyright: zero
errors. One known LiteLLM asynchronous logging cleanup warning occurred. All
responses were scripted; model forecasting accuracy was not measured.
