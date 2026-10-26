# Recover actual shelf values from JSON-mode wrappers

2026-10-26, based on main `1a13eaee`, using the same Qwen3.5-0.8B Q4_K_M
CPU-only server and five threads as the full-visit investigation. The ordinary
production prompts, shelf images, planning, seeded purchase draws and shared
inventory are used. The entry-plan defects reported in the preceding full-visit
report are still open; no entry prompt or shopping choices change here.

## Observed failure and correction

The final 160-token baseline `visit-free-json-1792976940115080456` makes three
real HTTP calls in 25.14 seconds. Its shelf reply copies a JSON Schema, truncates,
and repeats the schema within the normal 320-token retry. There is no measured
interest and no purchase. A user-prompt reminder to return top-level actual
values (`visit-free-flat-glance-json-1792977057920480867`, three calls, 18.49
seconds) does not fix it and is withheld.

Removing display titles and default-answer examples from the shelf wire schema
preserves its actual constraints and produces a different, useful response:

```json
{"properties":{"product":"Mineral Water 500ml","number":1,"interest":9,
"reason":"The price tag is clearly visible and yellow, indicating a very low price, which is ideal for a thirsty shopper."}}
```

The compact-schema-only prototype
`visit-free-compact-glance-json-1792977117715447522` takes two calls and 10.26
seconds. It still fails validation because the actual fields are under
`properties`. This is not a definition containing a `default` or `enum` value.

The correction keeps product enums, badge enums, score bounds, string limits and
required fields on the wire, while removing titles/defaults that the tiny model
copies. Its response validator unwraps a single `properties` container only
when no real top-level fields exist. Ordinary validation then decides whether
those values are usable. It never reads a choice from schema definitions,
recursively unwraps arbitrary containers, supplies a missing score, or changes
the choice. Existing nullable narrative handling, name/badge resolution and raw
photo rules still apply. Successful cache entries contain canonical flat fields.

With both changes, `visit-free-json-1792977273489062712` makes two real calls in
3.28 seconds: the same wrapped actual values are accepted, the shelf score is 9,
and one physical unit is purchased and checked out for zero revenue. Its cache
was inspected and contains flat product/number/interest/reason fields. The
schema-constrained repeat `visit-free-json_schema-1792977279272101133` also has
one valid glance and one free unit (two calls, 13.85 seconds).

Both full-visit diagnostics **still exit with failure** because their entrance
shopping list is empty despite the explicit water intent. The shelf response
failure is fixed in this example; entry semantics are not. Timings include warm
server-prefix reuse and are not independent performance comparisons.

## Other boundaries

The repeated-offer probe now accepts `--structured-output json` as well as its
existing `json_schema` default. Its two placements share a name and SKU but have
different prices, mirrored left/right with the same badge-shuffle seed. It calls
the production prompt, response schema and offer resolver; it is not a full
visit and does not execute purchases.

In `shelf-offers-7-json-1792977328337371835`, both free KRW cases still emit
schema definitions and are correctly rejected. Both USD cases emit real values;
one selects the $1 offer, while the mirrored case selects the $50 offer and
incorrectly describes it as $1. The diagnostic stays failed. Structural recovery
is not evidence that the mini VLM understands every price or location.

In `shelf-offers-7-json_schema-1792977369111121113`, all four replies validate,
but only the left-side cheap/free offers are selected correctly (2/4), matching
the earlier seed-7 baseline count. The free-left explanation misreads the tag as
`#10,000원` despite selecting the free placement. The schema-mode diagnostic also
stays failed; no price-reading improvement is claimed.

The new focused regression tests pass the observed wrapped values through the
real LiteLLM/Instructor validation and caching path with an offline HTTP
transport, in both JSON modes, including zero-interest responses. They reject
missing scores, copied definitions, booleans, numeric strings, out-of-range
scores, invalid targets, recursive wrappers and number-only raw-photo choices.
They also preserve authoritative root fields. Before the application change,
six of 28 cases fail and 22 pass. An initial test compared the SDK's generated
subclass directly with the cached base class; it was corrected to compare their
canonical fields before recording this baseline.

Also integrated upstream `5878bbc3`: show saved run totals before playback has
started, and improve neighborhood-map legend and note readability.

Verification: 257 affected backend cases pass (6.97 seconds), strict Pyright
reports zero errors/warnings, and the server import smoke check passes. The
37 warnings come from LiteLLM logging coroutine cleanup. All 27 affected
frontend cases pass (7.65 seconds), with TypeScript and changed-file lint clean.
The production frontend build passes (20.02 seconds), with the usual chunk-size
and Babel-plugin timing warnings. Whitespace checks pass.
