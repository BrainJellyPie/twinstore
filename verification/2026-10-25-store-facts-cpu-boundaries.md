# Missing facts and misleadingly valid local-model answers

2026-10-25, main `ab2bf90a`. Actual Qwen3.5-0.8B Q4_K_M on CPU, five
threads, llama.cpp b11878, 8192-token context. All experiments use fresh
application caches and the running local server; timings are observations,
not benchmarks. No replies are mocked and no user projects are saved.

The existing production setup probe already found that the separate layout
choice works while the drafted facts can omit supplied hours, opening days,
location and currency. This iteration expands the committed probe to distinguish
missing information from partly supplied information:

- `setup-unspecified-ko`: Korean bakery description, no location or schedule.
- `setup-hours-only`: pet shop open 9–17, no location or opening days.
- `setup-days-only`: bakery on Saturdays and Sundays, no hours or location.
- `setup-location-only`: café in Kyoto, Japan, no opening schedule.

Each case checks business type separately from hours, days, currency and address.
It rejects invented addresses and campus details. These are diagnostic probes,
not a passing quality claim or a replacement for ordinary automated tests.

Several fact-extraction alternatives were tried in scratch space and **withheld**:

| Alternative | Actual finding |
| --- | --- |
| Required fields plus exact evidence quotes | An unspecified bookshop acquired hours 10–18, daily opening and USD. The model copied the entire description as each evidence quote, so substring validation did not prove that the claimed facts were supported. |
| Same evidence schema on a Korean pharmacy | Hours were read, but weekend opening became daily. The explanation exhausted the output budget twice; the experiment was interrupted during further bounded recovery. |
| Required compact fields with explicit `unknown` choices | Overnight and 24-hour examples passed, but the pharmacy lost its days and the unspecified bookshop acquired 24-hour daily opening and KRW. |
| Three boolean presence questions | Four of seven cases passed. Hours-only, days-only and location-only descriptions were incorrectly classified as supplying none of those facts. |
| Separate day, hour and place requests | Day-only English input worked, but unspecified hours were still invented. Korean weekend days were missed and currency could be returned without an address. |
| Separate requests with bilingual hints and explicit examples | The unspecified English bookshop improved, but the example's 11–19 hours leaked into unrelated descriptions that supplied only days or location. |

The nullable-hour request was inspected on the wire: both `integer` and `null`
were present in its JSON schema. These results do not establish a grammar or
JSON parser bug. Requiring every field, matching copied substrings, or adding
examples alone is insufficient to validate the model's factual interpretation.
No prototype extraction schema, prompt, default, or postprocessing rule is
applied to production.

Scratch evidence under `/workspace/scratch/cpu-vlm-probe/`:

- `setup-unspecified-evidence-json_schema-1792969862720062585`
- `setup-*-explicit-json_schema-*`: four completed examples (the first unknown
  case used a bookshop-specific prompt example; later cases used a generic rule).
- `setup-presence-1792970075744077119`: seven mixed-information cases.
- `setup-single-fact-1792970127440751691`: six cases, three requests each.
- `setup-single-fact-examples-1792970219546566888`: the same six with examples.

Two further image experiments also remain withheld. Compressing empty shelf rows
kept the original repeated-offer result at 2/4, while changing the apparent shelf
geometry. Asking for a brief price observation before the numbered selection
matched 7/8 mirrored and renumbered offers, versus 5/8 in the earlier baseline,
but still chose a $50 offer instead of the explicitly requested $1 offer in one
case. Its explanations also misread free tags as 2,000 won or badge `#10`.
This is not reliable price understanding, so no renderer, glance schema or
glance prompt changes are shipped.

Image evidence: `shelf-offers-compact-7-1792970325341102840`,
`shelf-offers-reason-first-7-1792970382273153582`, and
`shelf-offers-reason-first-8-1792970462685988565` in the same scratch directory.
These call the glance and resolver, not a complete visit or purchase execution.

This iteration integrates upstream `1e34a8e1`, which formats a finished physical
run's start time in the selected app language.

The new production cases exposed wrong business choices too:

| Case on the preceding main | Calls | Seconds | Result |
| --- | ---: | ---: | --- |
| Hours-only pet shop | 2 | 18.42 | Correct pet-store layout; stated 9–17 hours omitted |
| Days-only bakery | 2 | 8.81 | Correct bakery type; weekends omitted and a campus name invented |
| Kyoto café | 2 | 8.77 | Bakery layout selected; supplied location and currency omitted |
| Korean unspecified bakery | 2 | 23.34 | Convenience-store layout selected; unspecified facts remain unset |

Runs: `setup-hours-only-json_schema-1792970612942819593`,
`setup-days-only-json_schema-1792970634211133706`,
`setup-location-only-json_schema-1792970646084749190`, and
`setup-unspecified-ko-json_schema-1792970657579339389`.

A short request choosing among the 24 business types classified twelve Korean,
English, French, Japanese, Spanish and Chinese examples correctly. Always
reselecting the layout within that business was withheld: it changed an otherwise
correct night convenience store into a cinema or tourist-area shop. Adding
descriptions and a general-purpose preference did not resolve that regression.
Evidence: `format-by-type-generic-1792970840171554760` and
`format-by-type-details-1792970893821800285`. The former's checks cover business
type only; the latter additionally rejects the unrelated night-store setting.
The earlier `format-by-type-1792970785361756189` used a bakery-specific hint and
incorrectly expected business type `florist`; the catalog's correct type is
`flowers`. Neither mistake is used as evidence for the final implementation.

The implemented guard therefore preserves the existing full-list choice when
its business matches the separate short classification. Only an incompatible
choice is repeated within the matching business, with short layout descriptions.
Unknown, missing or ambiguous business labels keep the original choice. A repair
that ignores its allowed business cannot become a valid final layout: name/ID
resolution is restricted to the matching templates. Existing form facts remain
unchanged. Every short choice permits one expansion from 160 to 320 tokens only
for a terminal typed output-cutoff error; other provider failures propagate.
An empty catalog or a catalog with one business skips classification.

The production-workflow scratch guard correctly selected the Korean bakery
(`setup-unspecified-ko-type-guard-json_schema-1792971009645039193`, four calls,
25.50 seconds), corrected Kyoto's business to café
(`setup-location-only-type-guard-json_schema-1792971038024200964`, four calls,
21.29 seconds), and preserved the night store's `compact_cvs` layout
(`setup-night-type-guard-json_schema-1792971062199961901`, three calls,
22.20 seconds). Only the first has all fact checks passing. Missing Kyoto
location/currency and night-store hours/days remain unresolved, as recorded in
each result. This change repairs the business choice, not all form extraction.

Final actual production reruns:

| Case | Directory | Calls | Seconds | Checked result |
| --- | --- | ---: | ---: | --- |
| Korean unspecified bakery, JSON-schema mode | `setup-unspecified-ko-json_schema-1792971286919827481` | 4 | 24.88 | Bakery selected; all fact checks pass |
| Kyoto café, JSON-schema mode | `setup-location-only-json_schema-1792971314718969874` | 4 | 21.47 | Café selected; location and currency still omitted |
| Night convenience store, JSON-schema mode | `setup-night-json_schema-1792971339211633262` | 3 | 22.71 | `compact_cvs` preserved; earlier fact omissions remain |
| Korean unspecified bakery, plain JSON mode | `setup-unspecified-ko-json-1792971364891060619` | 5 | 52.80 | Fails in the preserved first layout task, before business classification |

The last run is a separate unresolved format failure. The first fact response
wrapped actual values in `properties`, which the optional-field draft ignored.
The layout response then copied schema definitions and the complete enum instead
of selecting a format, exhausting both 160- and 320-token attempts. The new
business check was never reached. This is retained as evidence for the next
repair; plain-JSON setup generation is not claimed to be fixed here.

Twelve business-guard regressions failed before the implementation. Focused
verification covers 199 passing backend cases, including the final 22 guard
cases (blank/unknown layouts, missing/null/ambiguous types, preserved specific
choices, incompatible repair replies and bounded cutoff recovery). Strict typing
has zero errors or warnings and the backend boots. Five affected frontend tests,
TypeScript and changed-file lint pass; the production build takes 20.14 seconds.
Four existing LiteLLM logging cleanup warnings and the usual build size/timing
warnings remain. No full repository test suite was run.
