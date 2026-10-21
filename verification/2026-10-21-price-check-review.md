# Observed shelf / checkout price checks: verification record

Date: 2026-10-21. Repository: BrainJellyPie/twinstore; branch: feat/operator-modules.
Candidate rationale and checked sources: [candidate review](2026-10-21-price-check-candidates.md).

## Implementation

Market → Price checks connects two CSV uploads to project-scoped FastAPI preview/export routes,
application validation and a pure comparison engine. Full outer joins preserve missing observations.
Comparability requires matching SKU/package/currency, both observations on the declared date and public
terms. Integer minor-unit differences are exact; totals separate positive and negative sums by currency.
No model calls, inference about staff, sales losses, legal compliance, automatic corrections or stored reviews.

CSV exports contain both supplied observations, exclusions and currency totals, plus method, scope and a
digest of both length-delimited byte streams and scope. Changed bytes/scope return 409. Text formula prefixes
are escaped while signed numerical values remain numerical. Both originals should be retained.

## Basic verification, before the separate boundary phase

- `uv run pyright src/`: 0 errors, 0 warnings.
- Focused backend computation/API: 2 passed, 3.95 s.
- Focused frontend actual fetch/FormData/UI connection: 1 passed, 3.39 s.

## Boundary regressions and fixes

- Backend boundary run: 2 failed, 50 passed (4.31 s). Pydantic/FastAPI accepted form `audit_date=0`
  as 1970-01-01; export reported stale scope instead of invalid input. Both endpoints now require a ten-character
  ASCII YYYY-MM-DD string before date construction. Numeric epochs and impossible dates return 422.
- UI boundary run: 1 failed, 9 passed (2.79 s). Changing the valid checkout file hid an unresolved oversized
  label-file error. Errors are now tracked per source and survive changes to the other file.
- After fixes: backend 52 passed (4.40 s), frontend 10 passed (2.94 s). Additional maximum-union/date and
  actual Market navigation checks were added for the final verification below.
- Covered empty/header-only sources, all missing sides, duplicate IDs, repeated SKU checks, case-sensitive
  joins, simultaneous exclusions, conditional/unknown terms, both past/future dates, invalid/leap/extreme dates,
  zero and maximum prices, negative/fractional/nonfinite/scientific/non-ASCII numeric text, exact signed sums,
  malformed/duplicate/extra headers, malformed quoting, invalid UTF-8, BOM, Unicode, control characters,
  formula-leading text, limits of 2 MB/2,000 rows per source and 4,000 disjoint checks, null exports, changed
  scope/files/swapped sources, concurrent isolated reviews/exports, deleted projects, pending controls,
  stale UI results, failed requests, late responses/downloads and object URL cleanup.
- The first attempted boundary command was issued from repository root and ran no tests; the recorded red
  and green results are the corrected commands from backend/. No implementation failure is inferred from that invocation.

## Required full checks

Pending at the time this record was first written; final results will replace this paragraph before push.
Logs: `/workspace/.verification/twinstore-price-checks/`.

## Limits

All data are explicit offline test fixtures. No live-model calls, real-store observations, interviews, market
validation or real-device/browser usability study were run. UI checks use jsdom, API checks use FastAPI
TestClient and real project fixture storage. Same-date and same-ID assertions do not verify same-time,
same-channel or equivalent packages. The full union can contain 4,000 rows; browser-scale usability is not
certified. Prices exclude unsupported basket/weighted/member/multibuy calculations. A review has no revisions
or shared mutable state: concurrency protection here is source/scope-bound exports, not a saved-record lock.
No representative sampling or repeated-testing claim is made. Next different-domain candidate: dated
inventory-cost observations, followed by protocol-to-run linkage.
