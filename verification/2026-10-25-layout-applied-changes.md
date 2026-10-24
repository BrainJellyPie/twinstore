# Reject generated drafts that cannot apply any operation

The automatic layout/A/B validator resolved product and shelf names, then
discarded the operation list returned by the actual change executor. A
category-price change matching no stocked category, or a move to a locked,
outside-facing or current placement, could therefore yield a successful draft
without any applied operation. Such a variant could spend a simulation run
comparing an unchanged layout.

Use the executor's applied-operation list when validating each generated
variant. Drop variants with no applicable operation and retain their warnings.
If none remain, the existing structured-response validation requests bounded
model correction before caching. Layout editing shares that validation. Keep
variants with usable partial changes and their existing warnings. This does
not reinterpret ordinary price/promo assignments that the executor reports
as applied, nor change manually supplied experiment execution.

Before the fix, 45 regression cases failed and 15 controls passed in 3.60
seconds. Scripted HTTP exercises both JSON modes and both drafting paths:
missing/empty categories, empty shelves, locked faces, outer-wall faces and
already-current placement. Tests cover successful correction, repeated bad
responses, later recovery, cache reuse, mixed variants and source immutability.

After the fix, 174 focused engine, model-recovery, edit API and A/B API checks
passed in 8.47 seconds. Pyright reported zero errors and warnings. No native
model inference or model download was used.
