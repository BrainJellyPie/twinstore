# Preserve a model-generated price's currency when opening an A/B test

2026-10-26, based on main `13393319` and integration of upstream `5e8bcf7e`.
Actual local-model measurements use Qwen3.5-0.8B Q4_K_M, CPU only, five threads,
with the F16 vision projector and the existing 8K-context loopback server. No
paid provider, saved user project, mocked model answer or forced purchase is used.

## Reproduction and fix

The new online-report action opens a price variant in the physical-store A/B
builder. Its source result has a currency, but the handoff omitted it. The
experiment request model also had no currency field, so even an API caller that
supplied `currency: KRW` lost it during parsing. An otherwise valid USD layout
could accept the integer 3000 as $30.00. Checking that the layout and project
budgets agree does not check the imported prices' currency: online stores can
be created from a layout in a different currency.

`layout-price-krw-json_schema-1792981627153645093` executes the production
layout-drafting path on the actual CPU model. Its Korean request changes Green
Tea to 3,000 won and leaves everything else alone. In one call (3.14 s), the
model returns the correct `price: 3000`, and the applied result is
`Green Tea: price 5,000원 → 3,000원`. The price is valid in its original unit;
the transfer must retain that unit. Raw request/reply and before/after stores
remain in `/workspace/scratch/cpu-vlm-probe`.

The offline API regression uses this same integer amount with an existing USD
layout. Before the fix, each foreign-currency request starts a pending job
instead of returning an error. The corrected API compares the supplied source
currency to the effective layout currency inside the existing input-snapshot
lock, before creating a job or applying variants. It preserves the amount and
stores the canonical currency in successful requests. Older requests that omit
currency still use the layout's existing currency; they gain that currency in
their saved request without monetary conversion.

The online handoff now carries currency. The builder keeps it while editing,
does not display foreign minor units as local prices, and blocks execution on
a mismatched layout. Choosing a matching layout preserves the integer price;
replacing the draft through a new generated test or a recipe uses the current
layout's currency. This is a new test, not currency conversion. Duplicate-and-
edit also reads the report currency for older completed requests when available.
The mismatch explanation is translated into all six UI languages.

## Actual full online visit and unresolved survey failure

Added `local-online-session-probe.py`, which runs the real browser transitions,
rendered screenshots and VLM policy from arrival through the exit survey.
Technical validity, goal completion and manual semantic review are recorded
separately. The harness saves every request/reply, screenshot, action, session,
shopper and survey without HTTP headers.

`online-session-unavailable-mobile-json-1792981428355411362` gives a shopper
an explicit laptop-only goal in a clothing store. It takes three model-sourced
actions: opens a clothing category, searches for a laptop, then leaves with no
order. There are no rule fallbacks. Some thoughts contradict the chosen action
or invent details, so completing the no-purchase goal does not establish sound
reasoning.

The exit survey copies the schema instead of reporting scores. Its first
240-token response is truncated, and the existing 480-token retry copies the
complete schema. This is not a wrapped set of instance values: satisfaction,
ease and recommendation contain field definitions rather than measurements.
The application correctly rejects it and the saved survey is null. The full
probe records `technical_success: false`, five HTTP calls, 46.56 s and the
missing survey issue. This failure is retained for the next investigation;
no invented scores or survey-parser changes are included in this fix.

## Integration and verification

The upstream integration includes the online-to-store A/B handoff, immediate
timeline sizing, the taller format list, comparison-table styling and README
updates. The changelog conflict was resolved by retaining both branches' entries. Before
publication, main advanced to `6e955e82`, merging the same upstream changes plus
v0.8.1 release preparation. The fix was reapplied on that main, retaining its
release notes; the backend/frontend trees match the already-verified code.
The other reviewed development branch heads have no commits beyond this main.

The pre-fix focused checks reproduce eight backend failures and four frontend
failures (with four frontend passes). After the fix, 45 affected backend tests
pass (9.00 s) and 101 frontend tests pass (8.87 s). These cover foreign,
matching, lowercase and legacy currencies, no-job rejection, saved request
units, the online draft handoff, exact minor-unit round trips and replacement
of a mismatched draft by a freshly generated test. Strict Pyright, the server
import smoke check, TypeScript and changed-file lint pass. The production build
passes (20.63 s), with the existing chunk-size and Babel-plugin timing warnings.
Probe compilation and whitespace checks pass; no full backend suite was run.
