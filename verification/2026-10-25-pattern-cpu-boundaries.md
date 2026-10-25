# Actual CPU three-stage shopper investigation

Date: 2026-10-25. Qwen3.5-0.8B Q4, CPU, persistent local llama.cpp server.

The production pattern/intent/impulse engine was run on a generated compact store
with a customer requesting two named products. The baseline model narrated
purchases but returned navigation-only actions, so execution bought nothing.
Requiring action kinds in an experimental grammar caused repeated movement
coordinates until the 1,800-token reply limit. An operation-specific grammar also
ran out of room while repeating browse descriptions.

A shorter English instruction experiment produced the two intended planned
purchases, but also duplicate impulse purchases. Further USD/KRW checks did not
support shipping it: the final USD trial emitted only Enter, and the KRW trial
chose products whose descriptions disagreed with their identities. All these
experimental application and test edits were restored. The original three-stage
failure remains unresolved; completed JSON is not evidence of a correct visit.

Artifacts under `/workspace/scratch/cpu-vlm-probe/`:

- `pattern-USD-1792960631033963297`: baseline, zero purchases, 36.53 seconds.
- `pattern-USD-1792960734482245925`: required action only, truncated, 62.74 seconds.
- `pattern-USD-1792960880878429686`: operation grammar, truncated, 64.85 seconds.
- `pattern-english-USD-1792961070739276771`: English prototype, two planned plus
  two impulse purchases, 48.00 seconds.
- `pattern-USD-1792961195574865022`: final USD prototype, only Enter, 27.25 seconds.
- `pattern-KRW-1792961225379527694`: final KRW/free prototype, mismatched purchase
  narratives, 64.31 seconds.

An isolated product/quantity task then matched all four precise requests: ordinary
items and quantities, Korean items at the catalog's end, no purchase, and a free
offer. Initial evidence is `compact-purchases-1792961426935595352` (one actual call
per case, 1.56–3.14 seconds). This supports investigating smaller tasks; it does
not replace or validate the complete production engine.

Reproduce the isolated diagnostic with a local server already on port 8081:

```bash
PYTHONPATH=backend/src backend/.venv/bin/python verification/local-selection-probe.py
```

It builds the sample catalogs, saves inputs and raw replies without HTTP headers,
checks exact product codes/quantities and duplicates, and returns a nonzero status
on a mismatch. No user project is changed or paid model is called.

The earlier Korean shelf-name hallucination was also replayed with server
`cache_prompt` alternately true/false. All four replies named the same wrong
lighter on a water shelf (`cache-replay-1792960543491209720`). No server cache
configuration was changed: this experiment did not support cache reuse as the
cause of that recognition failure.

The committed standalone probe was rerun after replacing artifact-dependent inputs
with the built-in generator. All four exact selection checks passed again:
`compact-purchases-1792961958790107153`. These runs share a persistent server and
its prompt cache, so their elapsed times are not a general performance benchmark.
