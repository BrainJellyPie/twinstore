# Require explicit product targets in the local VLM response grammar

Date: 2026-10-25. Based on main `80119d71d6ffd5c5d4d6fdadd1d6ac7c6b413dea`.

An actual Qwen3.5-0.8B Q4 CPU run used the production compact-store generator,
entrance plan, rendered shelf images and VLM shopper engine. The entrance plan
identified two products, but both subsequent shelf answers omitted `product`
and `number` and returned only `interest: 6` plus a reason. The grammar required
only `interest`. Both answers failed semantic validation and became shelf errors,
so a run could complete while losing every visual impulse measurement.

The wire schema now requires `product`, `number` and `interest`. An explicit
no-choice answer uses an empty product, number 0 and interest 0. Existing parsing
still accepts identifiable name-only or number-only replies from providers that
do not enforce the grammar, older cached results, and explicit zero-interest
answers. Internal defaults and optional narration remain compatible. Positive
interest without an identifiable product remains an error.

The same actual USD example changed from two shelf errors to zero, with three
model calls in both cases. A second real example used Korean product names, KRW
prices and a free offer; both shelf answers also completed without format errors.
This does not prove correct visual understanding: one KRW reply named a lighter
while selecting the badge of a sports drink on the water shelf. The existing
number fallback resolved it to that drink. The raw image and answer retain this
remaining semantic failure; it is not counted as an improvement in recognition.

Evidence under `/workspace/scratch/cpu-vlm-probe/`:

- Baseline: `physical-USD-1792960193042713579` (22.66 seconds, two shelf errors).
- Fixed: `physical-USD-1792960295203687570` (7.12 seconds, zero shelf errors).
- Korean/free case: `physical-KRW-1792960304996820463` (22.95 seconds, zero shelf
  errors, with the name/badge mismatch above).

Timing is observational, not a benchmark; the persistent server can reuse prompt
prefixes despite each probe's fresh application cache.

Reproduce with the local multimodal model on port 8081:

```bash
PYTHONPATH=backend/src backend/.venv/bin/python verification/local-physical-probe.py
PYTHONPATH=backend/src backend/.venv/bin/python verification/local-physical-probe.py --currency KRW --free
```

The committed probe also executes the chosen customer actions, saves the resulting
purchases, and checks the engine's spending limit. `format_ok` is separate from
semantic quality; inspect `glance_targets`, images and raw replies. No user store
is modified and no paid provider is called.

The schema regression failed before the change. Focused checks passed afterward:
206 backend tests in 32.76 seconds, strict typing with zero errors/warnings, and
backend boot. Existing LiteLLM logging-cleanup warnings appeared in mocked tests.

The committed probe was also run with a USD free offer. It completed three actual
model calls with no shelf-format errors, then executed two planned purchases for
$3.78 within the spending limit. Evidence: `physical-USD-1792960479069068770`
(21.55 seconds). This checks execution and the presence of a free offer; the
customer did not purchase the free product.
