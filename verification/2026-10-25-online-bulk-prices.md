# Complete online-to-store price transfers

Date: 2026-10-25. Based on main `50d442ba053f02676011d93448c594e11017b67f`,
including the shareable report and suggested analyst questions. The numerical
evidence guard remains enabled after integration.

## Actual CPU reproduction

The production layout editor asked Qwen3.5-0.8B Q4_K_M, running on five CPU threads
with llama.cpp b11878 and no GPU offload, to lower the Drinks shelf's prices by
10%. The fixture contained 30 drinks plus an unrelated discounted snack. The
model correctly returned one `category_price` operation in one call.

The real conversion and application functions then carried that operation to an
online variant. The variant changed all 30 prices, but `run_store_changes` returned
only 20. Applying them back to the physical store left ten products unchanged.
Repeating the request returned the same first 20 and the advice “keep them with
another edit”; it provided no way to retrieve the omitted ten.

This was a downstream data-loss bug, despite a correct model response. It was
reproduced using actual model inference and the production snapshot reader with
isolated scratch data. No shopper simulation was needed for this price-transfer
case, and no saved user project was modified.

## Fix and boundaries

The transfer returns the complete list, within the same 500-change capacity used
for reviewed bulk product edits. Layout review and save accept that same limit.
A larger transfer fails explicitly before offering a partial edit. Its error is
visible in the UI and can be retried; it no longer makes the transfer controls
silently disappear.

| Stage | Before | After |
| --- | --- | --- |
| Prices changed by the generated online variant | 30 | 30 |
| Changes returned for review | 20 | 30 |
| Prices changed in the resulting physical store | 20 | 30 |
| Missing changes | 10 | 0 |

The final CPU run again used one model call. This fixes transfer completeness;
it does not expand the model's twelve-operation drafting limit or promise that
arbitrary natural-language instructions are interpreted correctly.

Reproduce with a separately running loopback CPU model:

```bash
PYTHONPATH=backend/src backend/.venv/bin/python verification/local-model-probe.py --case layout-bulk-bridge
```

The probe saves raw HTTP bodies without headers/keys, isolated online snapshots
and before/after physical stores. It checks all product fields and placements,
including preservation of the unrelated snack's reference price. Investigation
records are under `/workspace/scratch/cpu-vlm-probe/bulk-bridge-*`.

## Verification

Four backend cases and one frontend case failed before the fix. The final focused
checks cover 74 backend tests and 21 frontend tests: 21- and 30-product transfers
through the real review/save APIs, retry idempotency, unchanged source and
unselected products, the 500/501 boundary, visible/retryable errors, report HTML,
suggested questions and existing evidence validation. Product comparisons use
the domain's defaults when an older saved item omits its zero reference price.

Strict backend type checking passed with zero errors/warnings; backend boot,
frontend TypeScript, changed-file lint and the production build (20.73 s) passed.
When main advanced during verification, the patch was reapplied to the new main;
its source and test files were identical to the verified integration tree.
