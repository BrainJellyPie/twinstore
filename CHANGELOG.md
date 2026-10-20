# Changelog

## 0.2.0 — what changed and why

v0.1 produced plausible-looking shopper animations, but its numbers could not
support a decision: runs were not reproducible, two layouts were never compared
on equal terms, exposure ("what the shopper saw") was not computed on the route
actually walked, and baskets had no quantities, budgets or planned/impulse
distinction. v0.2 turns
the simulator into an experiment tool: every output is reproducible, paired
comparisons come with confidence intervals, and results can be scored against
real point-of-sale data.

All defaults changed by v0.2 can be switched back (see *Compatibility*).

### 1. Reproducibility and paired experiments

| Before | After |
|---|---|
| Per-customer mood/company cues drawn from an unseeded `random.Random()` | Every random stream (cue, arrival minute, timeline glances, engine seed) is derived from `(seed, replicate, persona id)` via `stable_seed` |
| Persona generation seeded the *global* `random` module while days ran concurrently | Local per-day streams |
| Two layouts saw different random customers | Same seed ⇒ same customers in the same states on every layout (**common random numbers**) |
| LLM calls not seeded, not cached | Optional per-call seed (`LLMConfig.seed`) and a content-addressed response cache (`LLMConfig.cache_dir`) |
| Failed customers silently dropped | Recorded with reasons in `diagnostics.json`, surfaced in the UI |

Each run now writes `output/manifest.json` (engine, model, seed, replicate,
exposure/ordering modes, layout and persona fingerprints, package version) and
`output/diagnostics.json` (failures, dropped hallucinated / over-budget buys,
buy-placement invariant violations).

### 2. Simulation correctness

- **Exposure on the walked route.** Stage-3 impulse candidates used to be
  computed on the stage-2 path *before* visits were re-ordered, i.e. on a route
  the shopper never walked. Exposure is now computed on the final route.
- **Visibility exposure model** (`exposure_model="visibility"`, default). A slot
  is visible from a path tile in front of its face, within `view_distance` tiles,
  inside a 45° cone, with clear line of sight. Score = shelf-level attention ×
  distance falloff; several facings of one SKU combine as 1 − Π(1 − v). The
  opposite face of a rack the shopper never walks past is not seen. Parameters
  live in `PerceptionConfig` and are explicit priors meant to be calibrated.
- **Planned ordering** (`route_ordering="planned"`, default). The shopper's own
  visit order is kept; impulse visits are grouped per rack and inserted at the
  cheapest detour. The legacy greedy nearest-neighbor re-ordering remains
  available as `"nearest"`.
- **Quantities and origins.** BUY lines carry `quantity`; `total_spent` is
  Σ price × quantity. BROWSE/BUY events carry `origin` = `planned` | `impulse`,
  so unplanned-purchase share is measurable.
- **No forced purchases.** Prompts state explicitly that leaving without buying
  is a valid outcome for patterns that allow it; impulse buys beyond
  `budget_max × budget_tolerance` are dropped (planned buys never are).
- **Currency.** `SimulationConfig.currency` (ISO 4217). Prompts describe prices in
  the right unit (e.g. KRW integers are won, not cents) and the UI formats money
  accordingly.

### 3. Engines

- `pattern_intent_impulse` (LLM): stage-2 prompt split into a static per-store
  system prefix (rules + compact catalog) and a short per-customer suffix. On the
  sample store the stage-2 call went from ~8,560 to ~7,090 tokens, of which
  ~6,760 are a prefix shared by every customer — so with provider/server prefix
  caching only ~330 tokens per call are new.
- `rule_based` (new, no LLM): calibratable heuristic shoppers
  (`RuleBasedConfig`) — pattern draw, category-matched planned purchases, and
  visibility-driven impulse buys and browse-only stops. 2,440 customers in ~7 s
  on 2 CPU cores. Use it for instant layout previews, as a research baseline,
  and for deterministic tests.

### 4. Analytics

`summary.json` keeps every v0.1 field and adds: buyers, conversion rate, units
sold, units per buyer, basket value, revenue per visitor, impulse revenue/unit
share, average visit time and path length, per-product and per-rack stats
(visitors, browsers, buyers, units, revenue), per-segment stats (age, gender,
purpose, identity) and hourly arrivals. `dwell_heatmap.json` holds seconds spent
per tile (the legacy `persona_heatmap` counts events).

- **Paired comparison** (`engine/analysis/compare.py`): per-customer metrics
  matched by persona; percentile bootstrap CI of B − A, P(B > A), and the number
  of customers needed to detect a 5% change.
- **Fidelity vs POS** (`engine/analysis/fidelity.py`): SKU and rack Spearman,
  JS similarity, NDCG@k, basket-size/value Wasserstein distances, mean and
  variance ratios (variance compression), hourly profile similarity. POS columns
  are matched by common aliases (`receipt_id`/`basket_id`, `sku`/`product_id`,
  `qty`, `unit_price`/`sales_value`, `timestamp`/`hour`, …).

### 5. API additions

| Endpoint | Purpose |
|---|---|
| `POST /api/projects/{pid}/runs` | now accepts `engine_type`, `seed`, `replicate`, `exposure_model`, `route_ordering`, `max_customers`, `preview` |
| `GET /api/engines` | engines with the server defaults |
| `GET /api/projects/{pid}/runs/{rid}/status` | adds `completed_customers`, `failed_customers`, `started_at` (live progress) |
| `GET /api/projects/{pid}/runs/{rid}/diagnostics` | diagnostics + manifest + token usage |
| `GET /api/projects/{pid}/compare?a=&b=` | paired A/B report |
| `POST /api/projects/{pid}/runs/{rid}/fidelity` | upload a POS CSV/XLSX, get the fidelity report |
| `GET /api/projects/{pid}/runs/{rid}/export.csv` | one row per simulated customer |
| `GET /api/projects/{pid}/runs/{rid}/heatmap` | adds `dwell_heatmap` |

**Preview runs** (`preview: true`) do not lock the setup and are allowed on
draft and finalized setups, so a layout can be iterated on and finalized layouts
can be re-run with other engines/seeds.

### 6. Headless CLI

```bash
cd backend
uv run parastore simulate --run sample_data/proj_67916afd/runs/run_ab0039 --engine rule_based --replicates 3 --out /tmp/runs/A
uv run parastore ab --store-a a.json --store-b b.json --personas personas.json --engine rule_based --out /tmp/ab
uv run parastore compare /tmp/ab/A/rep_0 /tmp/ab/B/rep_0
uv run parastore fidelity /tmp/runs/A/rep_0 pos_export.csv
uv run parastore summary /tmp/runs/A/rep_0
```

Run directories use the same layout as server runs.

### 7. Configuration via environment

| Variable | Field |
|---|---|
| `PARASTORE_LLM_MODEL` | LiteLLM model id, e.g. `anthropic/claude-sonnet-5-5`, `openai/local` |
| `PARASTORE_LLM_API_BASE` | OpenAI-compatible endpoint (vLLM, llama.cpp server, gateways) |
| `PARASTORE_LLM_TEMPERATURE`, `PARASTORE_LLM_MAX_TOKENS`, `PARASTORE_LLM_TIMEOUT_SEC` | sampling / limits |
| `PARASTORE_LLM_SEED` | enables per-call seeds |
| `PARASTORE_LLM_CACHE_DIR` | enables the response cache |
| `PARASTORE_ENGINE` | default engine (`pattern_intent_impulse` / `rule_based`) |
| `PARASTORE_SEED` | default run seed |
| `PARASTORE_CURRENCY` | ISO 4217 currency of prices |
| `PARASTORE_EXPOSURE_MODEL`, `PARASTORE_ROUTE_ORDERING` | `visibility`/`adjacency`, `planned`/`nearest` |
| `PARASTORE_BUDGET_TOLERANCE` | float, or `none` to disable |

### 8. UI

- Run launcher: engine (instant rule-based preview or LLM shoppers), customer
  sample, seed, replicate, preview vs final, LLM call estimate.
- Live progress (customers done, elapsed, remaining, failures); failed runs
  return to the previous view with the error shown inline.
- Playback toolbar: switch between runs of a layout, run again, compare, CSV
  export, back to editing (draft layouts list their previous runs).
- Compare dialog: paired bootstrap intervals as a forest plot, P(B > A), sample
  size hints, warnings when seeds or engines differ.
- Run KPI tiles, segment breakdown, diagnostics panel, POS validation upload.
- Heatmap layers — footfall, dwell time, predicted traffic — with color ramps
  and legend; 3D rack KPI overlay (revenue-intensity pads and labels).
- Quantity- and impulse-aware live metrics; currency-aware formatting.

### 9. Performance

A* results are memoized per (grid, start, end), rack access-tile geometry is
memoized per geometry key, and the rule engine tokenizes the catalog once per
run: same outputs, ~2.3× faster end to end on the sample store.

### Compatibility

- Old runs still load: new summary fields are optional in the UI; missing dwell
  heatmaps / rack stats disable the corresponding toggles.
- Behavior changes, each reversible: `exposure_model="adjacency"`,
  `route_ordering="nearest"`, `budget_tolerance=None`.
- `TimelineEvent.price` stays the unit price, so v0.1 consumers keep working;
  multiply by `quantity` for line totals.

## 0.1.0

Initial public release.
