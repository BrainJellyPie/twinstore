# Undefined VLM judge rank agreement

The earlier fidelity correction made constant-vector Spearman correlation
undefined. Auditing its other callers found that the layout judge rounded this
NaN directly and wrote `Spearman +nan` into report notes for three or more tied
candidates. Its in-memory report also retained NaN, although Pydantic's JSON
serialization converted the numeric field to null. Shelf sim-to-real agreement
already handled the undefined result.

The judge now records null and an explanatory note when correlation is not
finite. Defined correlations and candidate selection are unchanged. The report
model comment documents both insufficient candidates and constant scores.

Seven scripted judge cases cover each constant side, both constant, all-zero
outcomes, positive/negative correlation and nonconstant ties. Four cases failed
before the fix after correcting missing required test-fixture fields. All 85
focused judge/common-panel/missing-outcome/fidelity/zero-baseline checks passed
in 1.49 seconds; both modules pass Pyright. Strict JSON serialization of the
complete result rejects no non-finite values, and no note contains `nan`.
No real model calls, frontend build or full suite.
