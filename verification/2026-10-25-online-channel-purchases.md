# Keep free purchases and all visits in channel comparisons

Date: 2026-10-25. Integrates `ba3d0419df397735136793fb4c4e4a4d53ce3380`
on main `98dbc05b3469863f2e49eac840bb94f9e175d197`: store/online customer
comparison, its analyst facts, navigation changes and the shelf-photo drop zone.

## Actual CPU reproduction

The production layout editor asked the CPU-only Qwen3.5-0.8B Q4_K_M model for a
100% discount on Green Tea. Its actual response was applied to the store. The
production timeline builder then executed a controlled one-unit purchase at that
zero price. This is a purchase fixture, not a full physical shopper simulation.

The same fixture went online with free delivery. Forty real rule-policy sessions
were sampled from one project customer, exercising the supported case where the
requested panel is larger than the customer pool. Those sessions generated 21
orders and $27.00 of total payments. The channel service read the physical result
from isolated scratch files and the real online session summaries.

Before the fix, the physical purchase disappeared because the channel join tested
`total_spent > 0`. Online visits used a dictionary assignment per customer, so each
later visit replaced earlier purchase and payment records. Merely reordering the
same shopper records changed the customer from “neither” to “online only”, and
both orders showed $0 online spending instead of $27.

## Fix and final result

A positive purchased quantity identifies a free physical purchase. Positive spend
remains accepted for older records without purchase events. Repeated online
visits accumulate the customer's purchase flag and all payments. The join still
counts distinct shared customers and reads only the run's control store, not its
comparison variants.

Both orderings now give one customer who bought in both channels, $0 physical
spend, $27 online spend, and matching age/gender totals. The model-produced free
offer and real online sessions were rerun after the fix. No user project changed.
These are simulated channel outcomes; they do not establish real channel
preferences or equalize the number of visits in the two simulations.

Reproduce from the repository root, with the local CPU server already running:

```bash
PYTHONPATH=backend/src backend/.venv/bin/python verification/local-channel-probe.py
```

The probe runs the companion actual-model harness, writes the model's raw HTTP
bodies without credentials, and saves the physical result, online run and both
channel comparisons. Baseline: `/workspace/scratch/cpu-vlm-probe/channels-1792958493662321709`.
Fixed: `/workspace/scratch/cpu-vlm-probe/channels-1792958610166526174`.
Ten of twelve order/legacy boundary cases failed before the fix; the two accidental
passes were cases where the last visit happened to contain the only paid order.

## Verification

54 backend and 20 frontend tests passed. The twelve boundary cases cover all
six orderings of free-order, paid-order and non-purchase visits, with both free
physical purchases and legacy positive-spend records. The integration also checks
the channel API, analyst facts/evidence, conversation budget, quick-scan cohort,
report links and navigation. Strict backend typing reported zero errors/warnings;
backend boot, frontend TypeScript, changed-file lint and the production build
(20.15 seconds) passed. The standalone probe's CLI was checked after formatting.
