# Partial store descriptions: actual CPU failures and withheld changes

2026-10-26, main `42fd22df`. Qwen3.5-2B Q4_K_M, llama.cpp b11878,
CPU only, five threads, 8192-token context, temperature/seed zero, thinking
disabled. All model calls below were real loopback HTTP requests, with fresh
application caches. Timings are observations, not benchmarks; server prompt
reuse affects warm requests. Artifacts are under
`/workspace/scratch/cpu-vlm-probe-2b/`.

The production `draft_store_setup` pipeline failed all three new partial-fact
examples. Layout type/ID resolution succeeded, but the form facts did not.

| Input / artifact suffix | Calls | Seconds | Actual problem |
| --- | ---: | ---: | --- |
| Pet shop, hours 9–17 / `setup-hours-only-json_schema-1792995780096139971` | 3 | 33.17 | Closing hour omitted, so the pair was cleared with a warning; invented daily opening and USD |
| Bakery, Saturdays/Sundays / `setup-days-only-json_schema-1792995816075421879` | 3 | 33.47 | Invented USD and a layout-derived description of bread displays and dining groups |
| Cafe, Kyoto/Japan / `setup-location-only-json_schema-1792995852575808068` | 4 | 38.95 | Lost the location and invented daily opening; narrative added interiors/menu details |

Inspection found that the first fact-extraction request included the entire
layout catalog, with its own hours, interiors and products. Its wire schema
also allowed closing time to be omitted. Both are plausible contributors,
but changing them did not produce a reliable complete fix.

Withheld production-path experiments:

- Removed the catalog from the first request, required explicit nullable fact
  fields, and clarified the prompt. Seven actual pipeline cases ran in
  `setup-*-json_schema-1792996149955845239` through
  `setup-pharmacy-json_schema-1792996260484081451`. Closing time and currency
  improved for the hours-only input, but daily opening was still invented.
  Kyoto acquired 0–24 hours and lost its address. Korean cases lost addresses
  and sometimes selected wrong days. The days-only case originally reported
  success despite an unexpected hour warning; that was a probe false positive.
- A field-by-field prompt made city/district copying explicit. Seven more
  pipeline cases ran from `setup-hours-only-json_schema-1792996323588713643`
  through `setup-days-only-json_schema-1792996431498056203`. Addresses improved,
  but the model selected weekdays for unspecified/weekend schedules and lost
  currencies. The sparse Korean bakery acquired invented 10–20 hours.

The following cheaper diagnostics called the real production client and
setup schema for the **first extraction only**. They did not run layout
selection and are not full-pipeline results:

| Artifact directory | Change | Remaining counterexamples |
| --- | --- | --- |
| `setup-facts-examples-1792996502795373384` | Two explicit JSON examples, unknown facts and weekday hours | Kyoto/Seoul currency becomes null; 24-hour opening becomes 24–24; Korean bakery description is English |
| `setup-facts-examples-24h-1792996586938784708` | Replace the known-hours example with 24-hour opening | Hours-only becomes weekdays; weekend pharmacy becomes weekdays; currencies still null |
| `setup-facts-ordered-json_schema-1792996654531251998` | Rationale/location/currency before schedule/narrative on the wire | Currency improves, but unspecified schedules acquire weekdays and 10–18 hours |
| `setup-facts-plain-json-1792996683488614451` | JSON mode with the field-by-field prompt | Same semantic day/currency errors; 24-hour opening becomes 24–24 |
| `setup-facts-no-catalog-json_schema-1792996898634063487` | Original prompt/schema, only remove the catalog context | Hours-only still loses closing time and invents USD/days; stated locations/hours are omitted |

A separate small-task prototype, `setup-small-facts-1792996790609592105`,
made two actual calls per input for seven inputs: a schedule object and a
location/currency object. Explicit `not_stated` choices did not solve the
problem. Unspecified days became `every_day`; Korean 18:00 became 6, 20:00
became 8, 24-hour opening became 24–24, and Tuesday-only became all weekdays.
The location task retained only Mapo district, dropping Seoul. These were
prototype tasks, not a production pipeline change.

All proposed application schema/prompt/task changes were reverted. No model
facts were silently overwritten to make the checks pass. Two temporary
structural tests failed against the original implementation; they were also
removed with the withheld implementation and are not claimed as passing
regressions. The prototype and HTTP traces remain in scratch for inspection.

The committed probe now rejects unexpected warnings on supported/unspecified
schedules and rejects a non-Korean description when Korean was requested.
These checks supplement value/identity assertions; they do not prove that
all free-form statements are grounded. The semantic failures above remain
open. JSON validity and a known layout alone are not success criteria.

Independent production layout-edit controls on the same 2B CPU model passed:
`layout-free-item-json_schema-1792997204233531476` (5.61 s),
`layout-full-discount-json_schema-1792997212862109810` (2.21 s), and
`layout-price-krw-json_schema-1792997218090732693` (7.08 s). Each made one
actual request with a fresh application cache; no layout-edit change was made.
