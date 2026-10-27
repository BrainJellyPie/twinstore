# Withhold intent-location changes that regress free-item decisions

The impulse location fix is on main. The analogous intent-stage candidate
adds exact per-block/face target coordinates while preserving the existing
product table. Its geometry tests pass and actual local-model browse
locations improve. However, a full free-product visit changes a planned
pickup into an impulse pickup. A receipt-only check initially hides that
regression because the same free tea still appears on the receipt.

**The intent-stage production changes are withheld.** Main retains the
previous intent prompt. The committed change is the reusable probe: it now
also checks that an explicitly requested purchase appears in the initial
plan, and adds a customer who refuses to take even free items. Original
artifacts are preserved; separate review files apply the stronger check to
earlier results.

## Actual CPU experiments

Qwen3.5-2B Q4_K_M through llama.cpp b11878, five CPU threads, no GPU,
context 8192, reasoning disabled and temperature zero. All eleven visits
run real pattern selection, intent, impulse and receipt execution: 33 HTTP
calls in total, with zero application cache hits. These are text tasks on
the vision-capable model.

| Candidate / control | Case | Seconds | Purchase/attribution result |
| --- | --- | ---: | --- |
| Exact intent locations | Free tea, native | 41.11 | Correct receipt, but requested tea becomes an impulse buy: fail |
| Exact intent locations | Paid tea, JSON | 54.37 | Correct planned purchase and location; no impulse action |
| Exact intent locations | Paid tea, rotated shelf, native | 38.08 | Correct planned purchase and both browse locations |
| Exact intent locations | Absent laptop, native | 34.17 | No purchase or checkout; browse locations correct |
| Add a zero-price instruction | Free tea, native | 30.72 | No tea taken: fail |
| Same instruction | Browse without taking free items, native | 24.35 | Unwanted free tea added by impulse: fail |
| Define buy as adding to basket | Free tea, native | 30.04 | No tea taken: fail |
| Experimental `take_free` wire action | Free tea, native | 31.24 | No tea taken: fail |
| Same experimental action | Browse without taking free items, native | 32.56 | No purchase or checkout |
| Restored current main | Free tea, native | 37.06 | Exactly one planned free tea and checkout |
| Restored current main | Browse without taking free items, native | 25.91 | No purchase or checkout |

The `take_free` experiment changes only a scratch model-facing schema and
maps explicit zero-price references back to the existing buy action. It
also fails the positive case and is not introduced into production. Neither
successful negative cases nor accurate geometry justify accepting the failed
positive purchase cases. These observations are selected examples, not an
accuracy benchmark. Main still has the known intent-stage browse-side error;
the restored main controls do not establish complete narrative/spatial
correctness.

## Verification and artifacts

The candidate's new geometry test reproduces 35 failures before the change.
With that candidate, the geometry and compact-catalog checks pass 53 tests
in 3.74 seconds. Those are candidate checks, not evidence that its semantic
regressions are fixed. The candidate source and test are saved in scratch;
no failing test or candidate production edit is left in the repository.

The final production files are byte-identical to integration 449. Backend
tests/types/boot and frontend checks are inherited from integrations 449
and 448; they were not rerun for this diagnostic-only change. The updated
probe compiles and is exercised by the two restored-main controls. Diff
checks pass. Published v0.8.2 notes and assets remain unchanged.

Artifacts are under `/workspace/scratch/`:

- `intent-face-locations-final` and `intent-face-locations-rotated`: first
  candidate, including the free case's stricter `review.json`.
- `intent-free-plan-final`: first free-item instruction and its negative
  control; `intent-free-basket-definition`: revised buy definition.
- `free-take-contract`: experimental schema/verb runs;
  `probe_free_take_contract.py` records the experimental adapter.
- `free-taking-current-main`: fresh restored-main controls.
- `intent-face-locations-pure-candidate-stage2.py`,
  `intent-free-rule-candidate1-stage2.py`,
  `intent-free-rule-candidate2-stage2.py`,
  `intent-face-locations-candidate-test.py`, and
  `intent-face-locations-withheld.patch`: candidate sources and tests.

Reproduce the stricter controls with
`verification/local-intent-probe.py --case free --mode json_schema --full`
and `--case free_browse --mode json_schema --full` against the CPU server.
`planned_purchases_ok` must pass as well as combined purchase/receipt checks.
Narration remains unscored; per-stage browse-location diagnostics are separate.
