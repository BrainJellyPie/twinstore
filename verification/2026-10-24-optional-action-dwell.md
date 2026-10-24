# Preserve visits with unspecified action dwell

The generated action model accepts an omitted dwell value as zero, but rejected
explicit null. A local response with valid purchases and one unspecified browse,
payment or exit duration therefore failed the entire visit. Generated actions now
normalize only null dwell to the existing zero default before the inherited duration
clamp. This applies to both planned and impulse actions, including buys.

Intent and impulse prompts explicitly request zero when no duration is specified.
The route/timeline layer still uses its existing rack-duration floors and caps;
zero is not a new zero-duration event policy. Authored domain actions still reject
null dwell. Invalid non-null strings, booleans, containers and fractional values
remain rejected at the strict model boundary. Required buy quantities/SKUs and
navigation requirements are unchanged.

The pre-fix run failed 24 cases with 35 controls passing. Expanded tests exercise
both HTTP structured modes, planned/impulse stages, null dwell on its own or mixed
with unused non-buy fields, buy/non-buy parsing, immutable input data, real purchase
quantities and spend, checkout, exit and cache reuse. Related narration, duration
scaling, action-boundary, budget and unreachable-purchase checks also pass:
314 cases in 6.65 seconds. Strict Pyright: zero errors. Responses were scripted;
no live inference was used.
