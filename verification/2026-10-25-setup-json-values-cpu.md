# Actual values, schema echoes and quoted hours on the CPU model

2026-10-25, based on main `5f5522cf`. Qwen3.5-0.8B Q4_K_M, CPU only,
five threads, llama.cpp b11878 and an 8192-token context. These are actual
production-workflow or explicitly identified scratch-prototype requests, with
fresh application caches and no saved user stores.

The preceding production plain-JSON run
`setup-unspecified-ko-json-1792971364891060619` failed after five calls and
52.80 seconds. Its fact reply wrapped real values inside `properties`. All
optional fields were then silently left empty by the draft parser. Its layout
reply copied the entire schema enum instead of selecting an ID, exhausting both
160- and 320-token attempts before the business-type guard was reached.

An explicit one-key answer example in the choice prompt stopped that enum echo:
`setup-unspecified-ko-instance-json-1792971598240478174` completed three calls in
27.43 seconds. However, the wrapped fact values were still lost; the diagnostic
correctly failed. The probe now also rejects a lost name or description, since
valid JSON and a chosen layout do not establish that a useful form was drafted.

Unwrapping only the value object exposed a second real format error:
`setup-pharmacy-instance-values-json-1792971768749107870` failed twice on
`open_hour: "10"` and `close_hour: "18"`. The real SDK validates integer fields
strictly; quoted integers are not automatically accepted. Both complete replies
contained the supplied name, location and hours.

The recovery prototype unwraps `properties` only when real top-level fields are
absent, then applies the ordinary field validation. It never interprets schema
`default`, `enum` or descriptions as selected values. Explicit top-level data has
precedence over an extra wrapper. Non-object wrappers and nested schema field
definitions fail validation. Only exact signed decimal integer strings are
converted for hour fields; no floats, times with colons, units, booleans or
scientific notation are guessed or rounded. Existing hour-pair validation still
clears unsupported overnight or out-of-range values with a warning.

Two completed scratch runs after the integer handling:

| Case | Directory | Calls | Seconds | Remaining factual errors |
| --- | --- | ---: | ---: | --- |
| Korean pharmacy, plain JSON | `setup-pharmacy-instance-hours-json-1792971893408023414` | 3 | 14.65 | Weekend opening becomes daily; name, location, 10–18 hours, KRW and pharmacy layout survive |
| Unspecified Korean bakery, plain JSON | `setup-unspecified-ko-instance-hours-json-1792971910952351224` | 3 | 26.94 | Model invents daily 24-hour opening and KRW; name/description and bakery layout survive |

These are output-shape and completion results, not factual-quality passes. The
decoder preserves the actual model values, including the remaining mistakes; it
does not infer corrected hours or days. Timings are observations, not benchmarks,
because the persistent model server can reuse prefixes.

Fourteen focused regressions failed before implementation and thirteen existing
strict-value checks passed. The SDK fixtures exercise flat and wrapped replies,
quoted hours, all four business-choice stages, both JSON modes, canonical cache
contents, invalid schema definitions, root-field precedence and hour boundaries.

The final candidate keeps the fact prompt change to one sentence requesting
values instead of schema, while the small choices show explicit one-key JSON
answers. It changes prompt cache identities, so previously cached empty drafts
from the old parser are not reused. The shorter fact instruction was checked in
JSON-schema mode too: the unspecified Korean bakery still passes all checks
(`setup-unspecified-ko-values-minimal-json_schema-1792972085146589769`, four
calls, 27.41 seconds), and the night store keeps `compact_cvs` with the same
remaining fact omissions (`setup-night-values-minimal-json_schema-1792972115623876453`,
three calls, 21.96 seconds). The pharmacy plain-JSON candidate completes in three
calls, 28.74 seconds (`setup-pharmacy-values-minimal-json-1792972140596254269`),
with weekday interpretation still requiring correction.

Integration includes upstream `a228cfe6`: designer replies name mentioned options
that were not set, model waits display the request and elapsed time, dark brand
colours remain visible, and singular channel-fact wording is corrected. The
designer's mention detection is a text-pattern aid, not exhaustive semantic
validation of its explanations.

Focused verification passes 255 backend cases and 74 frontend cases. Two API
assertions tied to the old prompt's last sentence were changed to check that the
language instruction remains present; the 29-case API suite then passes. Strict
backend typing has zero errors or warnings, the server boots, TypeScript and
changed-file lint pass, and the production frontend build completes in 19.89
seconds. Four existing LiteLLM cleanup warnings and the usual bundle-size and
plugin-timing warnings remain. No full test suite was run.

Final production plain-JSON reruns both return their drafted form in three calls:

| Case | Directory | Seconds | Result |
| --- | --- | ---: | --- |
| Pharmacy | `setup-pharmacy-json-1792972397509973331` | 29.88 | Name, description, location, integer 10–18 hours and pharmacy layout survive; days still incorrectly say daily |
| Unspecified bakery | `setup-unspecified-ko-json-1792972430442929921` | 26.44 | Name, description and bakery layout survive; invented schedule/currency remain model errors |

The saved cache was inspected: parsed values are flat, hour values are integers,
and no `properties` wrapper is stored. Both diagnostic runs intentionally remain
failed on their factual checks. The earlier five-call schema-echo failure is
recovered, but these are not claims that the model's proposed facts are correct.
