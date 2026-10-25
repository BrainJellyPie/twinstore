# Repeated customer label pools from real CPU inference

Production `generate_batched` ran against Qwen3.5-0.8B Q4_K_M with llama.cpp b11878,
CPU only, five threads, one slot, 8,192-token context, JSON Schema, temperature 0,
seed 0 and a 4,096-token response limit. Each case used a fresh cache. The workflow
made real model calls for the area profile, hourly visitor estimate and customers.
It wrote two sample customers for Monday 09:00–10:00, with generation seed 4;
the estimated remaining visitors were filled with explicitly marked twins.

## Reproduced defect

For a Korean neighborhood shop the model emitted 40 identity entries containing
only three distinct labels, repeated a lunch keyword throughout its 20 keywords,
and repeated its visit purpose. For a Japanese cafe it emitted 40 identity entries
containing only two distinct labels. These were accepted as lists of labels.

Repeated keywords and hourly types occupied separate positions in `random.sample`,
giving repeated model text unintended sampling weight. Duplicate profile identities
also bloated the next model request and the fallback hourly type allocation.

The profile and hourly models now strip blanks and deduplicate exact labels in
first-seen order. They preserve the spelling, visitor counts, validation limits and
empty-pool recovery. Cached responses pass through the same normalization. No extra
model requests are added. Labels that differ in spelling or case remain distinct.

Fourteen SDK transport cases failed before the fix and passed afterward, covering
both JSON and JSON Schema modes, repeated/blank/Unicode labels, hourly types,
unchanged customer totals, downstream prompts and cache reuse.

## Actual before/after observations

| Input | Identity rows sent to the traffic model before → after | Calls after | Time after |
| --- | --- | --- | --- |
| Korean neighborhood convenience shop, KRW 3,000–10,000 | 40 → 3 | 3 | 35.08 s |
| Japanese cafe, JPY 500–1,500, coffee/bakery categories | 40 → 2 | 3 | 32.46 s |

Both cases retained the estimated 150 visitors, two written samples, unique customer
IDs, Monday 09:00 arrivals and the specified budget range. The cafe retained only
the supplied preference categories. Raw responses and outgoing prompts are under
`/workspace/scratch/cpu-vlm-probe/persona-{neighborhood-krw,cafe-jpy}{,-dedup}/`.

The tiny model still produced weak free text: untranslated narratives, repeated
customer descriptions, inappropriate time references and business names used as
customer types. A shorter English profile-prompt experiment improved the Japanese
case but produced a nonsensical Korean identity, so the existing prompt remains.
The fix addresses duplicate label weighting; the checks do not establish realistic
customer behavior or accurate visitor estimates.

Reproduce using the checked-in harness and a running local server:

```bash
PYTHONPATH=backend/src backend/.venv/bin/python verification/local-model-probe.py --case persona-neighborhood
PYTHONPATH=backend/src backend/.venv/bin/python verification/local-model-probe.py --case persona-cafe
```

The harness saves wire requests/replies, the full population, written samples,
estimates and checks for missing customers, duplicate IDs, out-of-hours arrivals,
out-of-range budgets and preferences outside the supplied category list.
The committed `persona-cafe` case also completed successfully with a fresh cache:
three calls, 32.84 s, 2,085 prompt tokens and 969 completion tokens.

## Verification

260 focused customer-generation tests passed in 20.92 s. They cover label/traffic
grammars, blank and repeated pools, label length bounds, customer source context,
sample/probe counts, unique IDs and cache behavior. The existing LiteLLM asynchronous
logging cleanup warnings were emitted. Strict backend type checking passed with
zero errors/warnings; backend boot and the probe's command-line loading passed.
No frontend code changed.
