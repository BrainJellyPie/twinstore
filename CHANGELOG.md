# Changelog

## 0.3.0 — vision shoppers in a living neighborhood

v0.2 made the simulator an experiment tool. v0.3 widens what can be simulated and
who decides: vision-language shoppers now make every in-store decision (whether
to go in, what they came for, what catches their eye), on any model you connect
or an ensemble of them, in a store you can generate from ten retail formats, on a
day you describe, in a neighborhood you generate or import — and the same
shoppers judge layout optimizations and the value of the shop next door.

### Vision shoppers decide end to end
- **Planning at the door** (`plan_policy="vlm"`, default for vision runs): the
  shopper sees a rendered store directory map, reads today's situation and where
  it came from, and decides whether to enter and what to buy; items resolve to
  SKUs by name, then category. Scenario demand multipliers are not applied on
  top (no double counting); arrivals and budgets still come from the scenario.
- **Impulse picks at the shelves** as before (rendered faces, interest 0–10,
  seeded purchase draw), now with the plan in the shopper's basket context.
- **Models**: OpenAI, Anthropic, Google Gemini, Alibaba Cloud Qwen (Model
  Studio), OpenRouter, vLLM, Ollama, llama.cpp and any OpenAI-compatible
  endpoint; keys entered in Settings are stored only on the machine running the
  backend. Connection tests for text and vision.
- **Ensembles** of models as one population: *mixture* (each shopper is one
  model, weighted) or *vote* (every model looks at each shelf, majority wins).

### Situations
19 presets (heatwave weekend, typhoon, fine dust, payday Friday, exam week,
local festival, competitor opening, 1+1 drinks, supply disruption, lunch rush, …)
and an editor for weather, season, day type, events, promotions, stock-outs,
crowding and hourly traffic. Vision shoppers read the situation; the rule model
applies it as calibrated multipliers.

### Neighborhoods
Procedural towns (residential, university, business district, station area,
suburban, tourist, mixed) or a real OpenStreetMap area: homes, offices, schools,
stations, rival stores and other venues. Huff-style demand gives visitors per
hour, catchment and walking distance; runs can draw their visitors from the
town, each shopper knowing where it came from. Synergy: the numeric effect of
every venue on our visitors, plus a **vision check** that simulates the affected
visitors with and without the venue to measure the basket effect.

### Layout optimization
Hill climbing, simulated annealing or a genetic search over planograms and rack
positions, scored on a fixed shopper panel with common random numbers and
re-checked on fresh shoppers. **Vision judge**: the rule model proposes, VLM
shoppers walk the top candidates on one paired panel and pick the winner, after
an optional calibration of the rule model to a VLM pilot; the report shows rule
vs vision ranks, paired deltas with intervals and P(better). Jobs can be stopped.

### Stores and graphics
- Ten store formats generated as complete layouts with priced products (urban
  and compact convenience stores, campus store, station kiosk, gas station,
  drugstore, mini-mart, café-bakery, office lobby, tourist shop), in English/$ or
  Korean/₩, parallel aisles or racetrack loop.
- **Realistic 3D mode**: gondolas with price channels, glass-door coolers, chest
  freezers, counter with POS, glass storefront, instanced products with
  generated packaging and labels, soft shadows, optional GTAO/bloom/reflections.
- **Shopper view**: an eye-height camera that follows one shopper.

### Interface
A new interface with day and night themes, a navigation rail, a home screen with
an animated store, glass controls over the 3D view, and larger type throughout.

### Research
`research/vlm_bench/`: a benchmark of VLM shoppers on controlled shelves —
position bias (Latin square), merchandising levers, read-back accuracy, persona
and situation conditioning, robustness to corruption, image-vs-text modality and
cross-model agreement — with figures and paper tables regenerated from saved
data. `research/README.md` lists paper directions.

### Calibrated against real purchases
`research/validation/` runs the engines on households of dunnhumby's *The
Complete Journey* (and X5 RetailHero for demographic gradients), compares
simulated trips with held-out real trips (weeks and households never used for
calibration) and feeds what is wrong back into the simulator:
- **Visit times from data**: a weekday × hour traffic profile fitted from
  transaction times (`engine/generators/traffic_profile.py`). A POS export with a
  timestamp column uploaded as supplemental data now sets when personas arrive;
  asked directly, models put most visits on a few stereotyped hours.
- **Supermarket-sized trips**: store-kind-aware prompts, plans of up to 30 items,
  `basket_scale`, products per category, multi-unit purchases, priority-ordered
  shopping lists, and `Persona.basket_size` (a trip of known size) honored by
  both planners.
- **Long plans no longer fall back silently**: plan token budgets scale with the
  list length, with one retry on a cut-off answer.
- **Model Studio regions**: `DASHSCOPE_API_BASE` (or Settings) selects the
  region or workspace endpoint; Qwen's reasoning mode is switched off for shopper
  decisions.
- **Walking from pedestrian tracks** (ATC shopping center, 13,159 tracks): 1.04 s
  per tile (median per-shopper speed 1.12 m/s vs 1.13 real), diagonal steps
  without corner cutting (detour index 1.27 → 1.19), per-shopper pace
  (lognormal, sd 0.3); time runs in fractional seconds.
- **Prices shoppers can react to**: `SlotItem.regular_price` (a sale shows as
  "$2.39 (was $2.99)" on the shelf tag), every product's price in the vision
  planner's store directory (`directory_prices`), and a constant-elasticity
  price factor in the rule planner (`price_elasticity`, default −1.8). Before,
  neither engine responded to a 20 % price change (elasticity ≈ 0); now the rule
  engine gives −0.78 and Haiku, Qwen and GPT-6 Luna −1.4 to −1.6, between the
  item-level elasticity of M5 food sales (−0.70) and brand-level meta-analyses
  (−1.76, −2.62).
- **Trips that vary like real ones**: `Persona.category_rates` (share of past
  trips with each category; on each trip a seeded draw decides which of them the
  household has run out of, and the vision planner is told) and
  `Persona.basket_kinds` (categories on the same past receipt; the planner keeps
  the model's first K categories and fills the trip within them). Asked for one
  trip, models otherwise bought every staple every time (milk on 73 % of trips
  against 43 % on receipts) and spread six items over six categories; a
  classifier told such baskets from real ones (`research/validation/c2st.py`).
- **Product choice**: the store directory lists every product of a category in a
  random order per shopper (with three fixed examples, 87 % of planned products
  were those three); `Persona.usual_products` and `habit_prob` for repeat
  purchases, shown to vision planners and used by the rule planner.
- **Newer OpenAI models** (GPT-6): `max_tokens` is renamed to
  `max_completion_tokens` and unsupported sampling values are dropped, learned
  from the provider's error and retried. Reasoning is switched off for shopper
  decisions (`reasoning_effort: none`): with it on, reasoning tokens used up the
  glance budget and 90 % of GPT-6 Luna's shelf glances failed. A cut-off glance
  is retried once with twice the budget, and validation runs report glance
  errors next to plan fallbacks.

### Getting started
Double-click `Parastore-Windows.bat`, `Parastore-macOS.command` or
`Parastore-Linux.sh`: the launcher installs what it needs, builds the interface
once and opens the app in the browser (see QUICKSTART.md).

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

- `vlm_glance` (new, vision-language shoppers): the rule-based planner decides
  the planned visits; impulse decisions come from a VLM that is shown a rendered
  image of each well-seen rack face along the route (`engine/perception`: names,
  price tags, promotion ribbons, numbered badges, randomized numbering). The
  model answers as the persona (mood, basket, money left) with a
  schema-constrained JSON reply naming the most tempting product and an
  interest score 0–10; answers are mapped back by printed name first and badge
  number second. A seeded per-face draw turns the score into a buy
  (`buy_scale` × interest/10 × shelf-level weight), a look, or nothing, so small
  models' tendency to always say "buy" cannot set the purchase rate. Runs on a
  CPU with a small local model served by llama.cpp
  (`structured_output="json_schema"` turns the schema into a grammar, so even
  sub-1B models answer validly). Every glance is saved to
  `output/vlm_glance_meta.json` and summarized in the dashboard.
  Measured on 2 vCPUs (same 30 customers, seed 1, 41 identical glances):
  Qwen3.5-0.8B ≈ 9.5 s/glance, Qwen3.5-2B ≈ 22.5 s/glance, no failed or
  hallucinated answers; the two models picked the same product in 32% of
  glances, and the 2B model put 71% of its picks in the top shelf row (54% in
  the left column) — a reading-order bias to calibrate or study, not a shopper
  fact. Reading probe (name / price of a numbered product, 16 shelves):
  0.8B 63% / 69% at 640 px, 2B 94% / 100% at 512 px. Planner and impulse step of `RuleBasedEngine`
  are now separate methods (results unchanged) so engines can swap only the
  impulse step.

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
