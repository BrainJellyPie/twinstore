# Do not score missing shelf attention as zero

A shelf-test model response could contain a valid pick while omitting noticed.
The default empty list was accepted and cached, then counted as zero attention
and zero first-noticed share in a complete comparison pair. A missing measurement
could therefore manufacture a difference between the control and test shelves.

For a shelf with visible products, the model-only response now requires noticed
in both the schema and Python validation. The existing two-attempt correction
budget applies, and repeated failure excludes the pair through existing error
handling. The prompt asks for an explicit list, including [] for no attention.
Preserve explicit empty measurements, the internal ShelfAnswer default and an
empty shelf's deducible empty list. Pick and badge-membership validation remain.

Before the fix, 18 missing-measurement cases failed and four controls passed in
2.72 seconds. Scripted HTTP covers both JSON modes, omission from either or both
arms, corrected/repeated failures, legacy cache revalidation, later recovery and
cached repeats. Assertions check exclusion, exact picks and all three paired
shares, with an explicit required field in the JSON schema. Controls cover
explicit empty lists and empty faces with valid or invalid picks.

After the fix, 146 focused shelf, survey, conjoint and marketing API checks passed
in 14.87 seconds. Full source Pyright reported zero errors and warnings. No native
model inference or paid model calls were used.
