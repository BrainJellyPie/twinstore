# Preserve customers with unspecified optional preferences

One model-generated customer with `preferred_categories: null` or
`behavior_tendency: null` made the whole batch fail validation. After three
structured attempts, otherwise usable customers were discarded and an entire
generation could fail. Omission already selected empty defaults, so these two
explicit null values now have the same meaning. The prompt asks for an empty
list when no category list/preferences are provided and an empty string when
there is no distinct behavior to describe.

This normalization is limited to the two optional fields. Required identity,
demographic and narrative fields, missing customer records, budget values,
non-null invalid types and list/text length bounds still fail validation. It
does not manufacture missing people or change population filling.

Before the fix, 13 regressions failed and 21 controls passed. The real HTTP
transport tests cover both structured modes, null in the first/middle/last
customer of five, two weekdays, early and late visit hours, per-customer budgets,
unique IDs, no unnecessary retries, and cache reuse. Focused customer generation,
batch grammar, truncation/context recovery, sample/probe, budget, missing-day and
concurrency verification passed 229 tests in 5.74 seconds. Strict Pyright reported
zero errors. One existing LiteLLM logging-cleanup warning occurred. Responses were
scripted, with no live or paid inference.
