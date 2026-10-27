# Shopper filter format experiments: production unchanged

Prototype sparse condition rows and two-stage condition selection to reduce
unrequested criteria from the CPU model. These experiments change only the
scratch drivers; the production filter prompt, wire format and call count
are unchanged. Main retains fixes 431 and 433's product/shelf target checks.
The candidates are withheld because their successful cases do not remove
the demonstrated omissions, unwanted conditions and structural failures.

All **24 live runs / 39 HTTP requests** use Qwen3.5-2B Q4_K_M, llama.cpp
b11878, five CPU threads, no GPU, context 8192, reasoning off, temperature 0
and fresh application caches. They use the seven complete synthetic personas
and synthetic visits in `verification/local-filter-probe.py`. No live reply
is mocked or replayed. The probe compares both customer IDs and applied
criteria; getting the same IDs with extra criteria does not pass.

| Candidate | Live runs / HTTP calls | Complete semantic passes | Remaining failures |
| --- | ---: | ---: | --- |
| Sparse v1: typed field/value rows | 3 / 4 | 2 | one shelf name emitted as a string instead of an array |
| Sparse v2: accept a scalar name as one list entry | 8 / 10 | 4 | native empty conditions, invented `any` shelf, repeated spending field, reversed before/after |
| Sparse v3: explicit arrival operator and nonempty rows | 4 / 5 | 1 | unwanted shelf purchase condition, malformed free-purchase row, omitted upper time bound |
| Staged v1: choose canonical fields without a catalog, then fill only those fields | 4 / 9 | 3 | free-purchase request incorrectly selects shelf visitation and an unrestricted purchase default |
| Staged v2: choose natural-language condition names, then typed values | 5 / 11 | 2 | unwanted named-product constraints for a free purchase, empty requested exclusion, overlong generated label |

These are deliberately selected diagnostic cases with repeated requests
across candidates, not a representative accuracy benchmark. Twelve passes
out of twenty-four runs must not be presented as model accuracy.

Sparse v1 handles the 15:00:30–16:00 window correctly in JSON and native
schema modes. Sparse v2 additionally succeeds for a known shelf, a known
product and shelf-only nonbuyers in JSON, plus shifted second boundaries in
native mode. It still inverts a before-only request, and its native known-
shelf request returns an empty condition list and all customers. Sparse v3
fixes that before-only case but loses the upper bound in a two-sided window.
Those changes are not a safe general replacement for the existing format.

Staged v1 gets known-shelf queries right in JSON/native modes and the before-
only clock query right in JSON. Staged v2 gets the bounded second-precision
window and excluded-product query right in JSON. However, its free-purchase
native result adds named products: it happens to match the expected customer
in this fixture but fails the criterion check. Its shelf-only query fails
before value extraction because the generated group label exceeds 60
characters twice. No candidate's successful IDs override those failures.

One earlier sparse-driver invocation failed before inference with
`KeyError('#/$defs/TextCondition')`: custom Pydantic schema references were
not registered. The scratch driver was corrected to inline its definitions.
That zero-HTTP fixture error is excluded from the 24 live runs above.

## Artifacts

`/workspace/scratch/shopper-sparse-summary.json` and
`shopper-staged-summary.json` record exact paths, timings, replies' resulting
criteria and failures. Run folders are `shopper-sparse-candidate-fixed/`,
`shopper-sparse-candidate-v2/`, `shopper-sparse-candidate-v3/`,
`shopper-staged-candidate/` and `shopper-staged-candidate-v2/`. The original
zero-HTTP fixture error is in `shopper-sparse-candidate/`.

The frozen scratch drivers are `probe_shopper_sparse_v1.py`,
`probe_shopper_sparse_v2.py`, `probe_shopper_sparse_v3.py`,
`probe_shopper_staged.py` and `probe_shopper_staged_v2.py`. They run the
production matching/target guards with experimental wire adapters and delegate
to the standard probe. This commit adds only this report; existing main's
backend/UI checks remain applicable without another test or build run.
