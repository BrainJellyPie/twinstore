# Keep a browsing shopper's budget visible

Date: 2026-10-25. Integrates `fb689f59d80ee4f40c3b62ab2df58e1a29f5de41`
over main `ec8d4d95c3f2dcc127e831beccf4f73a07089ea4`.

The incoming branch adjusts reading time and shopper patience. It also replaces
the budget of browsing shoppers with “nothing planned” in live decisions and
post-visit interviews. A lack of a purchase plan does not remove the customer's
available budget, which is still used by the rule policy.

An actual Qwen3.5-0.8B Q4 model on CPU received a production-rendered checkout
screenshot, with a $19.99 shirt in the cart and a browsing shopper whose available
budget was $1. The baseline request omitted that amount; the model chose to place
the order (one call, 8.48 seconds). The fixed request includes both “Budget:
$1.00” and “No purchase planned.” The model then selected delivery/returns help
(one call, 7.01 seconds). Its thought said it would close the tab, so this remains
an action/reasoning mismatch. This observation verifies budget delivery, not
general shopper intelligence or a hard spending limit.

Both live and interview prompts retain the amount, including KRW formatting and
the existing zero-means-no-fixed-limit convention. Purchase-mission wording is
unchanged. The incoming patience/reading settings are illustrative simulation
parameters, not a measured calibration of real customer behavior.

Reproduce with the local multimodal model server running on port 8081:

```bash
PYTHONPATH=backend/src backend/.venv/bin/python verification/local-shopper-probe.py
```

The probe saves the screenshot, input customer/site, raw request and reply, and
the chosen action. HTTP headers are not recorded and the image URL is replaced
by its saved filename. Use `--device mobile` for the alternate viewport.

Raw baseline evidence: `/workspace/scratch/cpu-vlm-probe/browse-budget-1792959616811343650`.
Fixed evidence: `/workspace/scratch/cpu-vlm-probe/browse-budget-1792959708884203410`.
Three of six new prompt regressions failed before the correction; the others
preserve purchase-mission wording.

Focused verification: 85 backend tests passed in 17.18 seconds, strict backend
checking reported zero errors/warnings, and backend boot and probe CLI checks
passed. No frontend source changed in this integration.
