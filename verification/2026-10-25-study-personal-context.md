# Individual shopper evidence reaches automatic studies

Concept surveys, conjoint choices and shelf tests shared a persona summary
containing identity, demographics, description, visit-purpose label and budget.
It omitted the shopper's individual purchase intent, shopping habits and
preferred categories. Updating any of these fields therefore left the actual
model request unchanged; with the same respondent and seed, an old answer was
reused from cache. The model could not account for that evidence on a fresh call
either.

Scripted HTTP tests reproduced stale reuse in all 18 combinations of three
fields, three study types and JSON/JSON-schema output modes, in 3.93 seconds.
The response client and on-disk cache were real; only the HTTP server was fake.
No inference, downloaded model weights or paid API calls were used.

The shared summary now includes each nonempty field. Existing demographic,
description, purpose and budget text stays intact. The revised tests also clear
each field and verify a fresh request, while repeated unchanged personas still
reuse the cache. Shelf control/test arms preserve their independent requests.
All 329 focused evidence, survey, conjoint and shelf checks passed in 16.91
seconds. Strict backend type checking passed with zero errors, and
`git diff --check` is clean. This follow-up was prepared separately from the
v0.4.13 release candidate.
