# Deleted online resources and query state — 2026-10-25

Integrated online-shopping branch 9673dea7 (feature 99add318). Deleting a store
or run removes its cached detail queries and refreshes only the corresponding
list, avoiding refetches of deleted resources into 404 errors. Run removal also
drops replay queries under that run's cache key. Both changelog entries were
retained when resolving the merge conflict.

Validation: 29 targeted SiteDesigner, RivalReport and JourneyPlayer cases passed
in 5.09s; frontend TypeScript and changed-file ESLint passed. Production build
passed in 18.79s with existing chunk-size/plugin timing warnings. No backend
source changed, so backend checks were not repeated.

An independent pre-merge exploration of 1,000 deterministic offline online visits
covered 55,162 steps and 36 action kinds across templates, USD/KRW/JPY, devices,
finite/out-of-stock products, free prices, coupons, fees and checkout settings.
All serialized session states, replay option identities, purchased quantities
and recorded order totals passed the probe's invariants; 89 visits purchased.
This was an action-sequence probe, not a live model quality evaluation.
