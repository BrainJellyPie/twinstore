# Automatic products on a real JSON-mode CPU model

Date: 2026-10-25. Based on main `a212cb49`. Qwen3.5-0.8B Q4_K_M,
CPU only, five threads, llama.cpp b11878, 8192-token context. Actual calls use
the production assortment workflow, full catalog, generated layouts and a fresh
application cache. No replies are mocked and no user project is saved.

A compact Korean convenience store failed after **16 real HTTP calls and
189.35 seconds** in plain JSON mode (`compact-json-1792967608185906627`).
Three concrete harness problems were reproduced:

1. Its first category request contained 14,991 prompt tokens, exceeding 8192.
   The same complete catalog enum was repeated at each of ten rack keys in
   the schema that JSON mode appends to the prompt.
2. Small recovery tasks returned valid catalog choices together with schema
   annotations such as `title`, `type`, `minItems` and `maxItems`. Rejecting those
   extra fields discarded the valid choice list and stopped automatic products.
3. When asked for at most eight dairy products, the model returned ten valid,
   distinct SKUs twice. The one-product café example similarly returned eight
   valid products. Neither request completed through the old count recovery.

The category schema now shares its repeated enum through a root `$defs`
reference. Every exact rack key is still required, unknown keys remain forbidden,
and the same allowed category IDs are enforced. Factoring happens after Pydantic
resolves its own schema; adding unknown references inside its schema-extra hook
fails Pydantic's reference accounting. The production compact JSON request now
has **4,871 prompt tokens** and returns all ten expected sections in one call.

Recovery choice models accept advisory extra fields while keeping only the
required `choices` list. Their wire grammar still forbids additional properties;
runtime validation still checks the choice type, catalog membership, bounds and
uniqueness. Extra fields are neither used as choices nor written to the cache.

Only fallback SKU subset tasks may reduce a complete, oversized answer to its
first allowed maximum selections. The **entire** answer must first contain valid,
unique catalog IDs. Unknown or duplicate tail entries are rejected. No partial
JSON, missing answer or invalid value is rescued. Positional category arrays are
never shortened, because that would lose a rack assignment. Reductions are logged.
This is bounded selection recovery, not validation of the model's preferences.

Experiments before the final count recovery:

| Run | Result | Calls | Seconds |
| --- | --- | ---: | ---: |
| Original compact JSON | Failed; oversized schema and echoed annotation rejection | 16 | 189.35 |
| Shared-schema-only prototype | Category stage fits; valid annotated SKU fallback rejected | 6 | 89.27 |
| Shared schema plus annotation handling | Progresses to dairy; ten SKUs exceed cap eight | 9 | 116.59 |
| Compact JSON-schema mode | Completes with both production stages | 2 | 61.92 |
| Café JSON before count recovery | Eight SKUs exceed one-product cap | 6 | 80.74 |

Evidence under `/workspace/scratch/cpu-vlm-probe/`:

- `compact-json-1792967608185906627`
- `compact-json-shared-1792967830910587186`
- `compact-json-1792968147957199991`
- `compact-json_schema-1792968267643580259`
- `cafe-json-1792968332642139539`

The last two category stages preserve all supplied section suggestions. The ID
`water_sports` means Water & Sports Drinks in this catalog; it is not a sports
accessory assignment. The intermediate café process had loaded the helper before
the count recovery edit.

The probe now accepts `--structured-output json` as well as its default
`json_schema` and records that mode with each result. Reproduce against a running
local server:

```bash
PYTHONPATH=backend/src backend/.venv/bin/python verification/local-model-probe.py \
  --case compact --structured-output json --output /tmp/twinstore-local-probes
PYTHONPATH=backend/src backend/.venv/bin/python verification/local-model-probe.py \
  --case cafe --structured-output json --output /tmp/twinstore-local-probes
```

Timings are observations, not benchmarks: the persistent server can reuse
prefixes. The probe validates completion and placement; it does not prove shopper
realism or assortment preference quality. Product correction prompts can still
grow too large when normalized long SKUs are echoed back; existing smaller-task
recovery handles that failure, and compact correction payloads remain a separate
follow-up.

Final production JSON-mode reruns both complete:

| Fixture | Result directory | Calls | Seconds | Checks |
| --- | --- | ---: | ---: | --- |
| Compact KRW convenience store | `compact-json-1792968704276235442` | 14 | 147.67 | 12 unique rack assignments, 10 categories, every target stocked, valid 8–16-SKU lists |
| Japanese café, one SKU per category, no alcohol | `cafe-json-1792968854986689658` | 13 | 119.34 | Every assignment stocks exactly one SKU and no excluded category |

These are completion improvements. In particular the café does more successful
work than the earlier failed run; its elapsed time does not represent a speedup.
The two rejected oversized product-correction calls still appear before smaller
recovery tasks. The actual model's printed schemas and oversized SKU lists remain
in the saved traces, and the application logs each safe subset reduction.

Eight targeted annotation/context regressions failed before the change. Final
focused verification passes 187 backend tests in 5.34 seconds, strict typing with
zero errors or warnings, and backend boot. Six existing LiteLLM logging-cleanup
warnings occurred. Tests cover invalid tail entries, duplicates, strict choice
types, preserved positional category counts, cache behavior, exact/Unicode rack
keys, one and 100 racks, and both structured-output modes. No frontend source is
changed by this fix.
