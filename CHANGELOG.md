# Changelog

## 0.4.0 — TwinStore: the store's digital twin, from photos, in one click

The project is now **TwinStore**, built on intellicia's open-source Parastore (MIT). User-facing
text, the brand mark and the launcher use the new name; internal identifiers (`PARASTORE_*`
variables, storage keys, the Python package, the `parastore` CLI) keep working.

### Conjoint studies
- New **Conjoint** tab in the Market page: a choice-based conjoint on the project's personas. Define a product's
  attributes and levels plus price levels; each respondent gets their own level-balanced random choice tasks
  (2–4 versions, optionally "none") and answers them in one model call.
- A pooled multinomial logit (level dummies, one price slope, a constant for none, a weak ridge prior) gives
  centred **part-worths**, **attribute importance** and **willingness to pay**; intervals resample respondents.
  Importance by age group and gender, fit (hit rate vs chance, McFadden R²), verbatims and caveats.
- **Market simulator**: build a line-up of up to four products from the tested levels, move prices within the
  tested range and see logit shares of preference (and "none") and the first product's share-versus-price curve.
- Print-ready HTML report and a long-format CSV (one row per option shown) for re-estimation elsewhere.
  API: `POST/GET /api/projects/{pid}/conjoints`, `GET .../conjoints/{id}`, `.../report.html`, `.../export.csv`.

### Fixes
- Realistic shoppers no longer crash the 3D view when React remounts them (development StrictMode): the
  per-shopper animation mixer is no longer uncached while its actions are still reused.

### Shopper journeys and interviews
- Playback has a **Shoppers** tab: rank the run's shoppers (top spenders, left empty-handed, impulse
  buys, longest visits) or search, open one, and see their trip step by step — wall-clock time,
  shelf, product, impulse or planned, and the thought recorded at each step — with the walked path
  and numbered stops on a floor map. **Follow in 3D** jumps playback to their arrival and highlights them.
- Each first stop at a stocked shelf face shows **what the shopper saw** there (the vision shoppers'
  renderer of that face at run time); click to enlarge. API: `GET .../runs/{run}/racks/{rack}/faces/{face}.png`.
- **Interview**: ask that shopper why ("why didn't you buy anything at Snacks 1?"). A language model
  answers in the first person from the persona, the trip and the shelves they stopped at only, says
  so when they did not notice something, and cites the steps it means (hover to highlight them).
  Suggested questions come from the trip. Transcripts are kept per run.
- **Group interview**: one question to many shoppers at once — everyone who left empty-handed,
  impulse buyers, top spenders, buyers or a random sample (4–40). Each answers from their own trip;
  the answers are then coded into two to six themes, with counts computed from per-answer
  assignments (misnumbered answers go to "Other"). Click an answer to open that shopper.
  API: `POST/GET .../runs/{run}/group-interviews`, `DELETE .../group-interviews/{id}`.
  API: `GET .../runs/{run}/shoppers/{id}/journey`, `GET/POST/DELETE .../shoppers/{id}/interview`.

### Photo mode (path-traced stills)
- In the first-person shopper view, **DoF** traces through a physical camera focused on whatever sits
  at the centre of the frame (f/1.4, f/2.8, f/5.6), for a photographic depth of field.
- In the realistic 3D view, **Photo** path-traces the current view with three-gpu-pathtracer:
  global illumination, area-light shadows from the ceiling panels, a glossy floor, real glass and
  daylight through the storefront. It refines sample by sample (64 / 256 / 1024) and saves a PNG;
  orbiting or zooming restarts it. The live scene is copied into a static one the path tracer can
  read: instanced packages baked with their label UVs, shader-patched materials replaced by plain PBR,
  the contact-shadow decal dropped, the BVH built in a worker.

### Marketing studio
- **Field POS reconciliation**: preview anonymous transaction/SKU rows against saved field assignments, distinguish
  positive evidence, conflicts and missing links, and send proposed purchases through the existing reviewed import.
  Duplicate item rows and transactions shared by assignments are rejected within a file. No automatic nonpurchase
  imputation, enrollment changes or overwriting of known outcomes; no model calls or raw POS persistence.
- **Field collection checks**: default pilot monitoring view with staff/shift and A/B completeness denominators,
  recording-gap checks, unrecorded-tail counts and a filtered, paginated follow-up checklist. JSON and CSV contain
  outcome availability rather than purchase values. Imports and closure refresh the checklist; older and locked
  pilots are supported. No significance tests or automatic outcome imputation.
- **Observation import review and history**: full-sheet change previews, explicit reasons and confirmation,
  file/revision-bound application, and retained before/after records with CSV export. Known-value clearing,
  enrollment removal and purchase reversals are flagged. Unchanged sheets do not create revisions; older pilots
  disclose missing historical coverage. API imports now require a preview token and reason.
- **Field pilot sample planning**: conservative power bounds aligned with the final 95% Hoeffding interval,
  required encounters and operating days, explicit capacity shortfalls, and optional even allocation across
  existing staff/shift blocks. Assumptions and a server-calculated assessment are saved with each new plan;
  existing pilots remain fixed. No model calls or real-sales forecasts.
- **Observed field pilots**: fixed staff/shift A/B assignment sheets from saved scripts, full-sheet CSV imports,
  immutable stimulus snapshots, intention-to-treat purchase counts, missingness bounds, versioned atomic updates,
  and locked closure. Complete targets receive a conservative fixed-sample conversion interval; unfinished targets
  stay descriptive. The independent Field pilots tab retains results after deletion of a source screening job.
- New **Market** page (`/marketing/<project>`) for marketers and research agencies, with seven tabs: A/B tests,
  shelf tests, concept tests, conjoint, staff scripts, field pilots and products.
- **Staff scripts**: independent A/B exposures on the same synthetic personas, with purchase intent,
  trust and pressure ratings, complete-pair bootstrap intervals, exploratory segments and customer replies.
  Saved product/persona snapshots and exact-script CSV support review; missing responses, restart recovery
  and conservative screening recommendations are explicit. API: `POST/GET /api/projects/{pid}/staff-pitches`,
  `GET/DELETE .../{id}`, `.../{id}/export.csv`. This is wording screening, not a real sales-effect estimate.
- **Products**: a product image library (multi-file drop, background cut-out, name, brand, linked shelf
  SKU, rename, delete), shared with Shelf Lab. The vision shoppers' shelf renderer draws a linked
  image instead of the plain package.
- **A/B tests**: variants of a saved layout — price, discount with a was-price tag, promotion sign,
  move to a fixture / shelf level, new pack, category price with .99 endings — plus one-click recipes.
  All arms run on the same persona panel and seed (common random numbers); store and focus-product
  outcomes come with paired bootstrap 95 % intervals, a winner only when the interval clears zero,
  and CSV export. API: `POST/GET /api/projects/{pid}/experiments`, `GET/DELETE .../{eid}`.
- **Price sweep**: a one-click recipe tests a product at −30 %, −15 %, +15 % and +30 % with the current
  price kept as the shoppers' reference (`keep_reference`), and the result shows its demand curve —
  units per 100 visitors with 95 % intervals at each price, product revenue, the elasticity across the
  arms and the revenue-maximising tested price (in the app and the report). Rule shoppers react to
  price relative to the usual price, so a new everyday price without a reference gets a note.
- **Duplicate and edit**: open any finished A/B or concept test as a pre-filled new one.
- **By segment**: every A/B variant also reports its paired difference to control within each age
  group and gender (20+ shoppers) for revenue per visitor and tracked-product units, with 95 %
  intervals, in the app and the report.
- **Automatic report** for every finished A/B test: a summary with a rule-based recommendation
  (roll out the winner with its daily and monthly revenue range, flag variants that lose, call out
  product-only lifts, the panel size needed to see a 5 % change), the test design, results with
  paired 95 % intervals and charts, tracked products, best sellers per arm, method and caveats.
  One self-contained, print-ready HTML page (print to PDF) and Markdown; a model can add a labelled
  commentary written from the report's numbers. API: `GET .../experiments/{eid}/report.html|.md`,
  `POST/DELETE .../experiments/{eid}/narrative`.
- **Shelf tests** (virtual shelf impact test): pick a shelf and a product, give it a new pack, price
  or sign, and preview both shelves live. The same respondents see the control and the test shelf
  through a vision model (badge numbers shuffled per respondent), pick the one product they would take
  and name what caught their eye first. Results: the product's pick share, noticed in the top three
  and noticed first, control vs test with paired 95 % intervals; what everyone took; why. API:
  `POST/GET .../shelf-tests`, `POST .../shelf-tests/preview`, `GET/DELETE .../shelf-tests/{id}`,
  `GET .../shelf-tests/{id}/{control|test}.png`; a print-ready report at `.../shelf-tests/{id}/report.html`.
- **Concept tests**: personas (with age / gender quotas) answer purchase intent, appeal, value,
  stand-out, Van Westendorp price and preference questions about up to four images through a vision
  model; Likert summaries, Wilson shares, price-sensitivity curves, segments, verbatims, CSV export,
  and a print-ready report (board, summary, answer distributions, price curves, segments, method).
  API: `POST/GET /api/projects/{pid}/surveys`, `GET/DELETE .../{sid}`, `.../board.jpg`, `.../export.csv`.

### One icon, every OS
- `launcher/`: one Go source → `TwinStore.exe` (Windows, icon embedded, no console window),
  `TwinStore.app` (macOS universal, app files inside the bundle) and `twinstore` (Linux, adds
  itself to the app menu). Double-click → a live boot screen at `127.0.0.1:8000` → the app at the
  same address. uv is fetched into the launcher's own folder when missing; a second click reopens
  the running app; ⌘K → **Quit TwinStore** stops everything.
- Release workflow builds one archive per OS and smoke-tests the packaged Linux launcher.

### Works without an API key
- With no cloud key set, a notice under the command bar says so, and the Models page shows what
  this computer is (CPU, cores, memory, GPU) and which local vision model it gets.
- `application/hardware.py` reads the hardware (NVIDIA via `nvidia-smi`, AMD/Intel via sysfs or
  WMI, Apple silicon unified memory) and picks the largest model that runs at a usable speed:
  - Qwen3.5-9B / 4B / 2B on a GPU (85 % of VRAM; 45 % of unified memory on a Mac);
  - Qwen3.5-2B, 0.8B or LFM2.5-VL-450M on a CPU, by cores and free memory.
- `application/local_vlm.py` downloads the matching llama.cpp build (CUDA for the driver's CUDA
  version, Metal, Vulkan or CPU) and the model, starts `llama-server` on 127.0.0.1, falls back to
  the CPU build if a GPU build does not start, and points the `llamacpp` provider at it.
- Launched from an app icon, this starts on its own (`TWINSTORE_LOCAL_VLM_AUTO=1`); otherwise one
  click on the notice or the Models page. `TWINSTORE_LOCAL_VLM=off`, `TWINSTORE_LLAMA_SERVER` and
  `TWINSTORE_LOCAL_VLM_MODEL` override it. API: `GET /api/system/models`,
  `POST /api/system/local-model/start|stop`.

### Situations
- Supermarkets, grocers and drugstores now use a **grocery profile** fitted to measured situation
  effects (`engine/grocery_priors.json`, `priors_for(store.type)`); convenience stores keep the old priors.
- Shoppers whose needs come from their history draw them scaled by the measured ratio of the
  situation (`ScenarioPriors.need_ratio`): more beer and snacks on a match day, more water in summer.
- **Time of day**: per-shopper part-of-day demand and needs by arrival hour
  (`ScenarioPriors.hour_demand`, `need_ratio["hour:evening"]`); no scenario needed.
- The scenario layer no longer files frozen pizza, cream cheese and candy bars under ice cream.

### Shopper behaviour
- Time at the shelf is lognormal (`RuleBasedConfig.shelf_time_median_sec`), on its own random stream so baskets do not
  change; a pick right after a look is no longer floored again by the rack minimum, and new racks
  start at a 2 s minimum.
- Each needed category names the household's usual products there, which raises repeat purchases.

### Shelf Lab — real photos as experiments
- Budgeted restocking quantities: verified stockroom counts, whole supplier packs, explicit priority,
  pack availability and a single delivery fee. The audit-linked API, worksheet UI and CSV export show
  unfilled demand, surplus, costs and constraints without placing orders or estimating sales recovery.
- Counterfactual edits on shelf photos (swap, stock-out, new package, price tag, promotion) with
  exact ground-truth masks: pixels outside the changed boxes are untouched.
- Sim2real: the same personas and seeds on the render, the tagged photo and the raw photo;
  decision agreement with confidence intervals, attention by shelf level, interest rank agreement.
- Compliance audit against the layout's reference face; stock-outs priced in revenue per day by
  paired simulation. Benchmark generator (`lab_cli bench`) and lever experiments.
- Rival shelf comparison: price index, assortment overlap, the rival's price-adjusted pull.
- Photoreal shelf studio (`frontend/studio.html`): a gondola bay rendered with Realistic mode's
  packages and a phone-photo finish, with exact facing boxes, so Shelf Lab can be shown and
  benchmarked on photo-like shelves. Edits now match light by the bright end of the surrounding ring
  (shelf edges, tags), so neighbouring products no longer tint swapped or refilled pixels.

### Photos in, twin out
- Floor-plan images (sketch, scan, PDF page) → walls, racks and doors on the grid, or read by a
  vision model.
- Storefront photos → appeal score → the venue's pull in the neighborhood model.
- Receipt photos → POS lines matched to the store's products → fidelity report.

### A new interface
- Aurora design system (Geist, Instrument Serif), command bar and ⌘K palette, redesigned home,
  workspace, wizard, neighborhood, capture and settings pages; photoreal 3D by default with a
  store environment map and lens effects; the playback bar folds away in the shopper's-eye view.

### Docs
- README rewritten around the twin, with system, vision-shopper, Shelf Lab, validation and
  launcher figures and a short film, all generated from HTML in `.github/assets/src`.
- License: TwinStore License 1.0 — free for research and non-commercial use, free for
  organizations with annual revenue up to US$1M, a separate license otherwise. The Parastore MIT
  notice is kept in full.

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

### Calibrated against real purchases
What a comparison with real trips exposed was fixed in the simulator:
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
- **Walking**: 1.04 s per tile, diagonal steps without corner cutting, per-shopper pace
  (lognormal, sd 0.3); time runs in fractional seconds.
- **Prices shoppers can react to**: `SlotItem.regular_price` (a sale shows as
  "$2.39 (was $2.99)" on the shelf tag), every product's price in the vision
  planner's store directory (`directory_prices`), and a constant-elasticity
  price factor in the rule planner (`price_elasticity`, default −1.8). Before,
  neither engine responded to a 20 % price change.
- **Trips that vary like real ones**: `Persona.category_rates` (share of past
  trips with each category; on each trip a seeded draw decides which of them the
  household has run out of, and the vision planner is told) and
  `Persona.basket_kinds` (categories on the same past receipt; the planner keeps
  the model's first K categories and fills the trip within them). Asked for one
  trip, models otherwise bought every staple every time and spread six items over
  six categories.
- **Product choice**: the store directory lists every product of a category in a
  random order per shopper; `Persona.usual_products` and `habit_prob` for repeat
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
