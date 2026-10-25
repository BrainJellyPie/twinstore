# Fix duplicate starter groups observed on the CPU model

## Actual failure and correction

The previous real CPU café probe completed structurally but repeated a bakery
group/rack in both bulk attempts. Its positional recovery then shifted categories
across shelf purposes. A further live experiment that fixed only rack assignments
exposed the same duplicate-group problem in **product** selection: bakery appeared
twice while gift confectionery was missing.

Both model-facing replies now use fixed-key objects:

```json
{"assignments": {"section_0": "coffee_station", "section_1": "bakery"}}
```

```json
{"selections": {"coffee_station": ["@P1"], "bakery": ["@P9"]}}
```

The actual request schema requires every known key and disallows extra keys. Each
rack value is a supplied category; each product array has that category's own code
enum and actual capacity. The small model no longer has to group IDs, remember
previous groups or infer where a positional answer belongs. This is not a fallback
that silently substitutes template products.

Validation aliases and before-validators convert wire maps to the existing internal
group representation. Old grouped/cache records remain readable. Full rack coverage,
unique categories/SKUs, the sixteen-category budget and category membership still
undergo semantic validation, including for providers that do not enforce JSON Schema.
Short product codes still bind to authoritative catalog SKUs using the mapping digest.

## Real production runs

Qwen3.5-0.8B Q4_K_M, F16 projector, llama.cpp b11878, CPU only/five threads,
8192 context, one slot, temperature/seed zero, thinking disabled, max output 5000.
The checked-in `verification/local-model-probe.py` ran production code with fresh
application caches and real HTTP replies. No concurrent test/build workload ran
during the two final observations below.

| Case | Before | Fixed production code |
| --- | --- | --- |
| 8×6 convenience store, KRW, Korean neighborhood description | 14 calls / 302.19 s; two truncated product responses | 2 calls / 61.90 s; 7,627 prompt + 1,011 output tokens |
| 10×8 café-bakery, JPY, Japanese description, one product/category, alcohol excluded | 5 calls / 77.53 s after the earlier short-code fix; recovery reordered shelves | 2 calls / 34.89 s; 7,050 prompt + 307 output tokens |

Both final runs had no retries, no truncation, and no store-validation issues.
Comparing every returned rack key with the supplied shelf-purpose hint found zero
mismatches in both runs. The café kept one product per category and excluded alcohol.
These are single-case observations, not a guarantee for every model or instruction.
The before/after café runs used the same inputs; the compact baseline predates both
the short-code and fixed-key improvements.

Session artifacts (raw requests/responses, chosen products and final stores):
`/workspace/scratch/cpu-vlm-probe/keyed-production/`. Re-run either case with the
commands in `2026-10-25-local-starter-cpu.md` against a CPU local server.

## Regression checks

1,041 focused tests passed in 35.56 seconds. The new keyed-response tests go through
the real LiteLLM/Instructor/OpenAI parsing path using controlled HTTP responses,
separately from the real-model evidence above. They cover missing/unknown rack keys,
duplicate normalized IDs, null/unknown categories, missing/extra product keys, null
product lists, cross-category codes, duplicate SKUs and canonical cache reuse.
Existing cases cover 1–100 racks, Unicode/quoted/path-like identifiers, currencies,
per-category capacity, large-task decomposition, exclusions and API failures.

Full backend source Pyright and server import checks are recorded with publication.
No frontend changes or full-repository test run were needed for this fix.
