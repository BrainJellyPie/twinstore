# Starter selection with a real small CPU model

## Reproduction

Actual production `LiteLLMClient` and `select_initial_assortment`, against
Qwen3.5-0.8B Q4_K_M plus its F16 vision projector, llama.cpp b11878,
CPU only (`-ngl 0`, five threads), context 8192, one slot. Temperature and seed
were zero, thinking disabled, JSON-schema output, maximum output 5000 tokens.
Each case used a fresh application cache. No model responses were mocked.
These starter tasks use the text capability of the VLM; separate package-image
probes also exercised its vision capability.

The baseline compact convenience store was 8×6, KRW, with Korean neighborhood
customer text. Its ten grouped rack IDs were initially assigned correctly, but
the model continued to sixteen category groups and repeated six IDs. The repair
repeated the mistake; positional fallback assigned unrelated baking categories
to the last two racks. Product selection then hit the 8192-token context limit
twice while copying long hashed SKUs. Per-category fallback finally succeeded.

| Same compact-store case | Calls | Elapsed | Prompt tokens | Output tokens |
| --- | ---: | ---: | ---: | ---: |
| Baseline | 14 | 302.19 s | 32,933 | 6,903 |
| Short codes and task bounds | 2 | 74.12 s | 7,539 | 1,221 |

The revised run had no correction/fallback calls, no truncation, and no store
validation issues. All ten categories matched the supplied shelf purposes.
`water_sports` is the catalog's **Water & Sports Drinks** identifier.
Elapsed times are single-run observations, not a benchmark; model prompt caching
and host load affect timings.

## Change and identity checks

- Category groups are bounded by the smaller of the rack count, allowed category
  count and sixteen. The prompt explicitly treats that bound as a ceiling.
- Model-facing product references are short codes. Both bulk and smaller recovery
  tasks resolve them to authoritative catalog SKUs before returning assignments.
  Category membership, capacity, uniqueness and full rack coverage remain enforced.
- A mapping digest participates in the request/cache identity, so unchanged visible
  names and prices cannot reuse a code for a different catalog SKU. Duplicate catalog
  rows share one candidate and code.
- 1,019 distinct focused tests passed across two runs (643 in 12.33 s and 389 in
  29.01 s, with thirteen overlapping primary-grammar tests). Coverage includes actual
  SDK wire formats, cache recovery, changing only SKU identities, three currencies,
  unknown/cross-category/duplicate IDs, 1–100 racks, capacity and API failure paths.
- Full backend source Pyright: zero errors/warnings. Server import smoke passed.

## Additional actual-model case and remaining work

A 10×8 café-bakery with Japanese customer text, JPY prices, one product per category
and alcohol excluded completed in five calls / 77.53 s without truncation. The final
store passed structural validation, used one product per category and excluded
alcohol. However, the first response duplicated the bakery group/rack and its
positional recovery reordered categories relative to the shelf purposes. This is
a separate observed quality problem to address next; structural success does not
prove that semantic assignments are correct.

The committed harness also ran an 8×6 bookstore with French customer text, USD,
two products per category and no food/drinks. It completed in two calls / 17.56 s
(3,718 prompt and 152 output tokens), selected only books and stationery, and
passed store validation. This exercises the checked-in harness itself.

## Run again

Start the local model on CPU, then from the repository root:

```sh
PYTHONPATH=backend/src backend/.venv/bin/python verification/local-model-probe.py --case compact
PYTHONPATH=backend/src backend/.venv/bin/python verification/local-model-probe.py --case cafe
PYTHONPATH=backend/src backend/.venv/bin/python verification/local-model-probe.py --case book
```

The harness routes the real provider client without changing saved settings. It
accepts only a loopback HTTP endpoint, creates a fresh cache per run and writes
`http.jsonl`, `result.json` and the final `store.json`. Review the actual choices
and prompts as well as the structural validation result. No headers or API keys
are written to the trace. The model server's CPU/GPU configuration must be recorded
separately; this client cannot infer it from the OpenAI-compatible endpoint.

Original session traces are under `/workspace/scratch/cpu-vlm-probe/` with case names
`starter-compact-neighborhood`, `starter-compact-codes` and `starter-cafe-one`.
