<div align="center">

<a href="./.github/assets/twinstore/twinstore-promo.mp4"><img src="./.github/assets/twinstore/twinstore-teaser.webp" width="100%" alt="TwinStore — the digital twin of your store"></a>

<h1>TwinStore</h1>

<p><b>The digital twin of your store, shopped by synthetic customers who can see.</b><br>
Rebuild a store from photos and plans, fill it with vision-language shoppers, and test every layout,<br>
price and promotion on the same people — before you move a shelf.</p>

<p>
<a href="https://github.com/BrainJellyPie/parastore/releases/latest"><img alt="Download" src="https://img.shields.io/badge/download-Windows%20%C2%B7%20macOS%20%C2%B7%20Linux-0b0c10?style=for-the-badge"></a>
<a href="./LICENSE"><img alt="License" src="https://img.shields.io/badge/license-free%20for%20research%20%26%20small%20teams-6b4dff?style=for-the-badge"></a>
<a href="./.github/assets/twinstore/twinstore-promo.mp4"><img alt="Watch" src="https://img.shields.io/badge/watch-49%20s%20film-e0429b?style=for-the-badge"></a>
</p>

<p>
<a href="#one-icon-every-os">Start</a> ·
<a href="#watch-it-run">Watch</a> ·
<a href="#what-you-can-do">Features</a> ·
<a href="#how-it-works">How it works</a> ·
<a href="#validated-on-real-baskets">Validation</a> ·
<a href="#for-researchers">Research</a> ·
<a href="#for-developers">Developers</a> ·
<a href="#license">License</a> ·
<a href="./QUICKSTART.md">한국어 빠른 시작</a>
</p>

<sub>TwinStore is built on <a href="https://github.com/intellicia-public/parastore">Parastore</a> by intellicia, released under the MIT License.</sub>

</div>

---

## Why TwinStore

- **A twin, not a mock-up.** Shelf photos become planograms, floor-plan sketches become the store grid, receipts and
  POS exports score the simulation, storefront photos set how many people walk in.
- **Shoppers that look.** Vision-language models see the shelf the shopper would see — a photoreal render or the real
  photo — read prices and promotion signs, and say what tempts them. Purchases are seeded draws, so two layouts are
  always compared on the very same people.
- **Answers with error bars.** Paired A/B runs with confidence intervals, a layout optimizer judged by vision shoppers,
  compliance audits priced in revenue per day, and a validation loop against real households' baskets.

## One icon, every OS

Download the archive for your computer from **[Releases](https://github.com/BrainJellyPie/parastore/releases/latest)**,
unpack it and double-click the **TwinStore** icon. The browser opens a boot screen with live progress and switches to the
app when it is ready. Nothing to install beforehand — the first start fetches Python and the packages (a few minutes,
once); later starts take seconds.

<table>
<tr>
<td width="56%"><img src="./.github/assets/twinstore/media/boot.jpg" alt="TwinStore boot screen"></td>
<td>

| Computer | Download | Double-click |
| :-- | :-- | :-- |
| Windows 10/11 | `…-windows-x64.zip` | **TwinStore.exe** |
| macOS 11+ | `…-macos.zip` | **TwinStore.app** |
| Linux x64 / arm64 | `…-linux-*.tar.gz` | **twinstore** |

Clicking the icon again reopens the running app. Quit with
<kbd>⌘K</kbd> / <kbd>Ctrl K</kbd> → **Quit TwinStore**.
First-time security prompts and details: [`QUICKSTART.md`](./QUICKSTART.md).

</td>
</tr>
</table>

No API key is needed to start: the sample store runs with the rule-based engine. Add an OpenAI, Anthropic, Gemini or Qwen
key — or a local vLLM / Ollama / llama.cpp server — under **Models** for language and vision shoppers.

## Watch it run

<table>
<tr>
<td width="50%"><a href="./.github/assets/twinstore/twinstore-promo.mp4"><img src="./.github/assets/twinstore/twinstore-promo-poster.jpg" alt="TwinStore film"></a><br>
<b>The film</b> · 49 s · what TwinStore is, in motion (<a href="./.github/assets/twinstore/twinstore-promo.mp4">MP4</a>)</td>
<td width="50%"><a href="./.github/assets/twinstore/twinstore-demo.mp4"><img src="./.github/assets/twinstore/twinstore-demo-poster.jpg" alt="TwinStore running"></a><br>
<b>The app, running</b> · 67 s real recording: ⌘K palette, 3D playback, heatmap, shopper's eye, Shelf Lab, neighborhood, night theme (<a href="./.github/assets/twinstore/twinstore-demo.mp4">MP4</a>)</td>
</tr>
</table>

## What you can do

<table>
<tr>
<td width="50%"><img src="./.github/assets/twinstore/screens/floor-light.jpg" alt="Photoreal 3D store with shoppers"><br>
<b>Photoreal 3D twin.</b> Shoppers walk the floor on a wall-clock day; scrub, pause, speed up, follow anyone.</td>
<td width="50%"><img src="./.github/assets/twinstore/screens/shopper-light.jpg" alt="Shopper's-eye view"><br>
<b>Shopper's-eye view.</b> The first-person camera shows what a shopper — and the vision model — sees.</td>
</tr>
<tr>
<td><img src="./.github/assets/twinstore/screens/heat-light.jpg" alt="Footfall heatmap"><br>
<b>Heat, dwell and traffic.</b> Footfall, dwell and predicted-traffic layers, rack KPIs in 3D, revenue by rack.</td>
<td><img src="./.github/assets/twinstore/screens/capture-light.jpg" alt="Shelf capture and Shelf Lab"><br>
<b>Shelf capture &amp; Shelf Lab.</b> A phone photo becomes a planogram; edit it counterfactually and audit it.</td>
</tr>
<tr>
<td><img src="./.github/assets/twinstore/screens/town-light.jpg" alt="Neighborhood demand"><br>
<b>The neighborhood.</b> Huff demand, rival stores, synergy with the shop next door, storefront appeal.</td>
<td><img src="./.github/assets/twinstore/screens/wizard-light.jpg" alt="New store wizard"><br>
<b>New store in two steps.</b> Ten retail formats, an address, opening hours — or start from a floor-plan image.</td>
</tr>
<tr>
<td><img src="./.github/assets/twinstore/screens/home-dark.jpg" alt="Home, night theme"><br>
<b>Day and night.</b> A command bar, <kbd>⌘K</kbd> palette for everything, light and dark themes.</td>
<td><img src="./.github/assets/twinstore/screens/settings-dark.jpg" alt="Model providers"><br>
<b>Any model.</b> Cloud APIs or local servers, text and vision, single models or ensembles.</td>
</tr>
</table>

## How it works

<img src="./.github/assets/twinstore/architecture.png" alt="Fig. 1 — TwinStore system: real-world inputs, twin builders, the twin, shopper engines, answers">

**Fig. 1 — System.** Photos, plans and sales data are turned into one JSON world per layout (store graph, personas,
situations, neighborhood, renderer, photo layer). Rule-based, LLM and VLM shoppers walk it on seeded days; results flow
back into calibration against real POS data.

<img src="./.github/assets/twinstore/vision-shopper.png" alt="Fig. 2 — How a vision shopper decides">

**Fig. 2 — Vision shopper.** At the door the model reads a directory map and today's situation and writes a plan
(`EntryDecision`); at each shelf it sees the face — rendered or photographed, with numbered tags — and rates the most
tempting product 0–10 (`ShelfGlance`). The purchase is a seeded draw from that rating, so a model's eagerness cannot set
the purchase rate, and paired layouts share every random number.

<img src="./.github/assets/twinstore/shelf-lab.png" alt="Fig. 3 — Shelf Lab: counterfactual photo edits with exact ground truth">

**Fig. 3 — Shelf Lab.** Swap products, empty a run, inpaint a new package, reprint a price tag or hang a promotion on a
real shelf photo. Only pixels inside the changed boxes move, so every edit has an exact mask. The same shoppers judge
the render, the tagged photo and the raw photo (sim2real agreement with CIs), and compliance gaps against the reference
layout are priced in revenue per day by paired simulation. Details: [`SHELF_LAB.md`](./SHELF_LAB.md).

### Photos in, twin out

| Input | What TwinStore does with it |
| :-- | :-- |
| Shelf photo | detects shelves and facings, reads names and price tags → a rack face in the planogram |
| Floor-plan image (sketch, scan, PDF page) | ink mask → walls, racks, doors → an 8–16 tile grid at 1.25 m per tile (or a vision model reads it) |
| Storefront photo | a vision model rates sign, entrance, window and upkeep → the venue's pull in the neighborhood model |
| Receipt photos | transcribed by a vision model, matched to the store's products → a POS export that scores a run |
| Rival's shelf photo | price index and assortment overlap against your layout → the rival's price-adjusted pull |

## Validated on real baskets

<img src="./research/validation/figures/fig_validation_evidence.png" alt="Fig. 4 — Evidence that the twin's shoppers shop like real ones, on held-out households of public datasets">

**Fig. 4 — Validation.** TwinStore's own engines shop for the households of six public datasets, and the simulated
trips are compared with real trips they never saw. The main test uses dunnhumby's *The Complete Journey*: 150
households and 14 weeks, held out, with Claude Haiku 5.5, Qwen 3.8 Flash and GPT-6 Luna as decision models. Every
failure the data exposed changed the simulator:
- visit times and trip size;
- silent fallbacks;
- shelf prices and price response;
- walking speed;
- trips that repeat the same staples.

| Check (held out) | Simulated | Real reference |
| :--- | :--- | :--- |
| Category mix of the population (JSD) | `0.017–0.018` | `0.012` (a household's own earlier receipts) |
| Per-household hit vs the store's best-sellers | `+0.027 to +0.035` (95 % CIs above 0) | – |
| Classifier AUC, real vs simulated receipt | `0.56–0.62` | `0.52` (own earlier receipt vs later one) |
| Own-price elasticity | `−0.78 to −1.60` | `−0.70` (M5) to `−2.62` (meta-analysis) |
| Bigger trips from farther away (Ta-Feng) | `1.25–1.36×` | `1.33×` |
| Walking speed (13,159 tracks) | `1.12 m/s` | `1.13 m/s` |

What failed, what was fixed, the limits and the reproduction steps are in
[`research/validation`](./research/validation). Every number there is recomputed from the saved trips.

## For researchers

Every stimulus and every model call is seeded and cached, so experiments are paired and reproducible, and figures
regenerate from saved JSON without model calls. [`research/`](./research) holds the instruments and paper directions:

- **VLM shopper bench** — position and order biases (Latin-square placement, shuffled tag numbers), merchandising
  levers, price read-back, persona and situation conditioning, corruption robustness, image-vs-text ablation, agreement
  across models (Fleiss' κ).
- **Shelf-to-planogram digital twins** — detection + VLM reading with exact ground truth, and *decision-preserving
  reconstruction*: does the simulator reach the same conclusion on the reconstruction as on the original?
- **Sim2real for shopper agents** — the same panel on renders, tagged photos and raw photos (Shelf Lab).
- **Expensive-oracle layout optimization** — a rule-based surrogate proposes, vision shoppers judge on a paired panel.

`uv run python -m store_emulator.lab_cli bench` writes a counterfactual benchmark (`index.jsonl` with images, masks and
edits) from rendered shelves or real captures.

## For developers

<img src="./.github/assets/twinstore/launcher.png" alt="Fig. 5 — One-click launcher">

**Fig. 5 — Launcher.** One Go source builds `TwinStore.exe`, `TwinStore.app` and `twinstore`. It fetches uv if needed,
starts the server on a private port, shows the boot screen at `127.0.0.1:8000` and then proxies the app at that same
address. See [`launcher/README.md`](./launcher/README.md).

```bash
cp backend/.env.example backend/.env   # add an LLM API key if you want LLM shoppers — never commit real keys
./scripts/dev.sh                       # backend on :8000, frontend on :5173
```

Requirements: Python **3.13+** with [uv](https://github.com/astral-sh/uv), Node **20+** with **pnpm 10.33.0**. The
optional Grounding DINO detector for shelf capture: `cd backend && uv sync --extra capture` (pulls PyTorch).

<details>
<summary><b>Run each side, build, launcher</b></summary>

```bash
cd backend && uv sync && uv run uvicorn store_emulator.server.main:app --reload   # API docs at :8000/docs
cd frontend && pnpm install && pnpm dev                                          # VITE_API_URL=… to point elsewhere
cd frontend && pnpm build                                                         # the backend serves frontend/dist
launcher/build.sh                                                                 # TwinStore.exe / .app / linux → launcher/dist
```

Verification (keep all green): `uv run pyright src/`, `uv run pytest` in `backend`; `pnpm build`, `pnpm lint`,
`pnpm test` in `frontend`. Conventions for contributors and AI agents: [`AGENTS.md`](./AGENTS.md).

</details>

<details>
<summary><b>Headless experiments (CLI)</b></summary>

```bash
cd backend
# re-simulate a saved run's store + personas with the LLM-free engine, 3 replicates
uv run twinstore simulate --run sample_data/proj_67916afd/runs/run_ab0039 \
    --engine rule_based --replicates 3 --out /tmp/runs/A
# paired A/B of two layouts on the same personas (common random numbers)
uv run twinstore ab --store-a a.json --store-b b.json --personas personas.json \
    --engine rule_based --seed 1 --out /tmp/ab
uv run twinstore compare /tmp/ab/A/rep_0 /tmp/ab/B/rep_0   # any two run dirs
uv run twinstore fidelity /tmp/runs/A/rep_0 pos.csv        # Spearman, JS, NDCG vs POS
uv run twinstore summary /tmp/runs/A/rep_0
```

The former command name `parastore` still works.

</details>

<details>
<summary><b>Vision shoppers on a CPU (no GPU, no API key)</b></summary>

The `vlm_glance` engine shows a vision-language model the shelves a shopper walks past — product names, shelf-edge
price tags, promotion ribbons and numbered badges. Any LiteLLM vision model works; the defaults target a small model
served locally by [llama.cpp](https://github.com/ggml-org/llama.cpp):

```bash
# Qwen3.5-0.8B (Q4_K_M) + its vision projector, ~1 GB RAM, 2 CPU threads
llama-server -m Qwen3.5-0.8B-Q4_K_M.gguf --mmproj mmproj-Qwen3.5-0.8B-F16.gguf \
    --port 8081 -c 8192 -np 1 --reasoning off --image-max-tokens 512 --cache-ram 256

cd backend
uv run twinstore simulate --run sample_data/proj_67916afd/runs/run_ab0039 \
    --engine vlm_glance --max-customers 30 --cache-dir .vlm_cache --out /tmp/runs/V
```

Measured on 2 vCPUs without a GPU (512 px shelf images, ~1.4 glances per customer):

| Model (Q4_K_M + F16 projector) | s / glance | Reads name / price of a numbered product |
| :--- | ---: | :--- |
| Qwen3.5-0.8B | ~9.5 | 58–63% / 50–69% |
| Qwen3.5-2B | ~22.5 | 88–94% / 100% |

Both favor products in the top row of a shelf image (2B: ~70% of picks) — treat VLM picks as a model to calibrate,
not as ground truth.

</details>

<details>
<summary><b>Configuration</b></summary>

Defaults live in `backend/src/store_emulator/application/config.py`; these environment variables override them (the
`PARASTORE_` prefix is kept for compatibility):

| Variable | Meaning |
| :--- | :--- |
| `PARASTORE_LLM_MODEL`, `PARASTORE_LLM_API_BASE` | LiteLLM model id and optional OpenAI-compatible endpoint |
| `PARASTORE_LLM_SEED`, `PARASTORE_LLM_CACHE_DIR` | per-call seed; on-disk response cache for repeatable LLM runs |
| `PARASTORE_LLM_TEMPERATURE`, `PARASTORE_LLM_MAX_TOKENS`, `PARASTORE_LLM_TIMEOUT_SEC` | sampling and limits |
| `PARASTORE_ENGINE` | default engine: `pattern_intent_impulse` (LLM), `rule_based` or `vlm_glance` (vision) |
| `PARASTORE_SEED`, `PARASTORE_CURRENCY` | default run seed; ISO 4217 currency of prices (e.g. `KRW`) |
| `PARASTORE_EXPOSURE_MODEL`, `PARASTORE_ROUTE_ORDERING` | `visibility`/`adjacency`; `planned`/`nearest` |
| `PARASTORE_BUDGET_TOLERANCE` | impulse-spend cap as a multiple of the persona budget (`none` disables) |
| `PARASTORE_VLM_MODEL`, `PARASTORE_VLM_API_BASE` | vision model for `vlm_glance` (default `openai/local-vlm` at `http://127.0.0.1:8081/v1`) |
| `PARASTORE_VLM_MAX_GLANCES`, `PARASTORE_VLM_GLANCE_POLICY`, `PARASTORE_VLM_LOOK_BASE` | shelves considered per customer; `gated`/`all`; look probability |
| `PARASTORE_VLM_IMAGE_WIDTH`, `PARASTORE_VLM_CACHE_DIR`, `PARASTORE_VLM_SEED` | shelf image width (px); response cache; per-call seeds |
| `PARASTORE_DATA_HOME` | for the launcher: folder that holds `.data` (projects, runs, settings) instead of `backend/` |

Running TwinStore with an AI assistant? Point it at [`USAGE.md`](./USAGE.md): the inputs a simulation hinges on, LLM
call counts per persona size, and the silent failures to catch before a run. History: [`CHANGELOG.md`](./CHANGELOG.md).

</details>

## Limitations

- **Calibrate before you trust numbers.** Out of the box the shoppers are plausible, not fitted to your store. Use the
  fidelity report against your POS data, read paired differences with their intervals, and see the validation loop for
  what calibration involves.
- **Model calls cost money and time.** A week of personas for a modest store can be hundreds of calls (capped at 100
  personas per day by default, `PERSONA_DAILY_CAP`). The rule-based engine and response caches make iteration free.
- **One store at a time.** No fleet view or multi-week dynamics; crowding is light (per-shopper paths, no queues).
- **APIs and data shapes may still change** between versions.

## License

**TwinStore License 1.0** — see [`LICENSE`](./LICENSE).

| Who | Allowed |
| :-- | :-- |
| Research (academic or in a company, not in production) and non-commercial use | ✅ free, unlimited |
| Commercial use by individuals and organizations with annual revenue up to **US$1M** | ✅ free |
| Everyone else | 📩 separate license — [open an issue](https://github.com/BrainJellyPie/parastore/issues) |

TwinStore is built on Parastore © 2026 intellicia, whose code remains available under the MIT License; its notice is
kept in full in [`LICENSE`](./LICENSE). Dependencies keep their own licenses
([`LICENSES-BACKEND.md`](./LICENSES-BACKEND.md), [`LICENSES-FRONTEND.txt`](./LICENSES-FRONTEND.txt)).

## Credits

- 3D assets in `frontend/public/assets/` are from [Kenney](https://kenney.nl), CC0 1.0 — [Mini Market](https://kenney.nl/assets/mini-market),
  [Mini Characters](https://kenney.nl/assets/mini-characters), [Graveyard Kit](https://kenney.nl/assets/graveyard-kit).
- Validation uses dunnhumby *The Complete Journey*, X5 RetailHero, Ta-Feng, Instacart, Favorita, M5 and the ATC
  pedestrian tracks; the capture benchmark's real-photo check uses ShelfWise "SKUs on shelves PL" (CC BY 4.0). None of
  these datasets are redistributed here.
- Figures and the film are generated from HTML in [`.github/assets/src`](./.github/assets/src)
  (`render.mjs`, `render-video.mjs`).

## Contributing

Issues and pull requests are welcome. Please keep changes focused, run the verification commands above, and follow
[`AGENTS.md`](./AGENTS.md). For commercial licensing, open an issue and we will reach out.
