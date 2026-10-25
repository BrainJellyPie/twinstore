# Recover customer batches below a small model's output ceiling

Date: 2026-10-25. Based on main `5b96fae5`.

An actual Qwen3.5-0.8B Q4 CPU run generated a night-market profile, traffic and
12 customer descriptions successfully at the normal 4,096-token output limit.
The store opens only on Monday at 23:00; the Korean source description specifies
3,000–10,000 won and drinks/snacks. The model wrote 12 original customers; the
existing population expansion filled its 150 estimated visits with twins. The
specified money, category and arrival constraints held. This is not validation
of its traffic estimate or descriptive realism: its generated label pool still
included lunch-oriented labels in this late-night scenario.

Using that same normalized area profile, a five-customer production writer with
a 512-token output ceiling failed. The initial request was truncated, a two-person
child succeeded, and the three-person child was also truncated. Recovery allowed
only one split, so the whole batch returned zero customers after seven real HTTP
calls and 97.94 seconds. No partial customer batch was accepted.

Output-truncation recovery now keeps dividing unfinished tasks until they fit or
reach one customer. A failed single-customer request stops the batch. The maximum
12-customer input bounds this to at most 23 task nodes, excluding the provider's
existing retries; no new retries are added for unrelated errors. Input-context
overflow still permits only the existing one split, since a shared oversized
prefix may not shrink. The shared concurrency slot is released before child
requests. Original offsets, visit hours, progress and batch atomicity are retained.

The identical actual five-person example then completed with five unique
customers, the supplied budgets/categories and all arrivals at 23:00. It used
nine HTTP calls in 114.85 seconds. This improves completion, not latency: it does
additional successful work instead of stopping after the second truncation.
Requests still use the configured output limit; it is not silently raised.

Evidence under `/workspace/scratch/cpu-vlm-probe/`:

- Normal full generation: `persona-nightmarket-1792963780069478258`, 3 calls,
  92.70 seconds, 12 originals and 150 total visits after population expansion.
- Before: `persona-token-limit-1792964007431615644`, 7 calls, 97.94 seconds,
  zero returned customers, one failed batch.
- After: `persona-token-limit-1792964143677071562`, 9 calls, 114.85 seconds,
  all five customers, no failed batch.

The persistent server may reuse prompt prefixes; these are observations rather
than benchmarks. Every probe used a fresh application cache. There were no paid
model calls or saved user-store edits. Raw inputs/replies without headers and
customer results are retained.

The focused batch probe embeds the normalized labels from the actual area run;
it calls the production customer writer with live model responses. Reproduce:

```bash
PYTHONPATH=backend/src backend/.venv/bin/python verification/local-persona-batch-probe.py \
  --count 5 --max-tokens 512 --output /tmp/twinstore-local-probes
PYTHONPATH=backend/src backend/.venv/bin/python verification/local-model-probe.py \
  --case persona-nightmarket --output /tmp/twinstore-local-probes
```

Nine selected recursive-recovery/atomicity regressions failed before the change.
The regressions exercise nested cuts down to one customer, mixed visit hours,
12-customer bounds, failed final children, write-choice probes, shared concurrency,
cache behavior and unchanged handling of context or unrelated errors.

The committed batch probe also ran two actual customers in different slots
(22:00 and 23:00): `persona-batch-1792964274771860027`, one call, 11.56 seconds,
both slots and budget limits preserved. Focused verification passed: 216 backend
tests in 19.74 seconds, strict typing with zero errors/warnings and backend boot.
The tests emitted 13 existing LiteLLM logging-cleanup warnings.
