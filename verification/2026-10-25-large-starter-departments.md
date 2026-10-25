# Preserve large generated-store departments during automatic stocking

Date: 2026-10-25. Reproduced on main `88ed17f6`; integrated with the later
research-note removal and online mobile/report release preparation.

An actual Qwen3.5-0.8B Q4 run on CPU used a 32 x 26 KRW hypermarket,
one product per category, alcohol excluded and a Korean neighborhood/family
description. Its 198 accessible racks form 51 selection rows with 44 suggested
categories. The model returned all 51 correct rack IDs and 44 categories twice.
The generic starter selector rejected both answers because it always capped
categories at 16. Its fallback eventually filled the racks, but collapsed the
assortment to 16 categories, replacing many unrelated departments.

Automatic template stocking now supplies its section count as the category
ceiling. The bulk validators, product groups and small-task category budget use
that ceiling consistently. The existing manual-refill default remains 16;
per-category SKU limits remain unchanged. A large ceiling permits a varied
assortment; it does not require one category per section.

The same real CPU example after the change accepted the first category answer.
The full product catalog exceeded the server's 8,192-token context, and the
existing recovery selected products in one-category tasks. The final result
contained all 198 racks exactly once, all 44 original categories, zero reassigned
racks, one SKU per category and no excluded alcohol. Store validation passed.
This demonstrates the stated structural and department checks for this fixture;
it does not establish general correctness of every model preference.

Evidence under `/workspace/scratch/cpu-vlm-probe/`:

- Before: `hypermarket-1792962076899732670`, 168.79 seconds, 10 HTTP calls,
  16 categories. The first two rejected answers took 42.055 and 33.451 seconds.
- After: `hypermarket-1792962684741753814`, 128.87 seconds, 47 HTTP calls,
  44 categories. Calls comprise one category answer, two context-limit responses
  and 44 small product selections. The larger assortment needs more product
  choices than the collapsed baseline.

Timings describe these runs, not a benchmark: the persistent server may reuse
prompt prefixes, although every probe uses a fresh application cache. There were
no paid model calls and no saved user stores were edited. Raw request bodies,
answers, the final store and the result summary are retained without credentials.

Reproduce with the local CPU server on port 8081:

```bash
PYTHONPATH=backend/src backend/.venv/bin/python verification/local-model-probe.py \
  --case hypermarket --output /tmp/twinstore-local-probes
```

Four regressions (bulk/small category selection crossed with bulk/small product
selection) failed before the fix and passed afterward. The existing near-cap
tests also exercise 16-, 24- and 40-category budgets, JSON/schema output modes,
17 through 100 rack rows and cached replies.

Focused verification passed: 479 backend cases across the initial run and the
affected-file recheck, strict backend typing (zero errors/warnings), backend boot,
11 online report/router tests, TypeScript checking and the frontend build.
Changed frontend files have no lint errors (two existing route-export warnings).
The checks also caught and corrected unnecessary one-row fallback batches when
the entire allowed catalog already fits within the category ceiling.
