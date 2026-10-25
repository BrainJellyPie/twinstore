<div align="center">

<a href="./.github/assets/twinstore/twinstore-promo.mp4"><img src="./.github/assets/twinstore/twinstore-teaser.webp" width="100%" alt="TwinStore — the digital twin of your store"></a>

<h1>TwinStore</h1>

<p><b>The digital twin of your store, shopped by synthetic customers who can see.</b><br>
Rebuild a store from photos and plans, fill it with vision-language shoppers, and test every layout,<br>
price, pack and promotion on the same people — before you move a shelf.</p>

<p>
<a href="https://github.com/BrainJellyPie/twinstore/releases/latest"><img alt="Download" src="https://img.shields.io/badge/download-Windows%20%C2%B7%20macOS%20%C2%B7%20Linux-0b0c10?style=for-the-badge"></a>
<a href="./LICENSE"><img alt="License" src="https://img.shields.io/badge/license-free%20for%20research%20%26%20small%20teams-6b4dff?style=for-the-badge"></a>
<a href="./.github/assets/twinstore/twinstore-promo.mp4"><img alt="Watch" src="https://img.shields.io/badge/watch-the%20film-e0429b?style=for-the-badge"></a>
<a href="./TwinStore_Technical_Report.pdf"><img alt="Technical report" src="https://img.shields.io/badge/read-technical%20report%20(PDF)-1f7a5c?style=for-the-badge"></a>
<a href="https://arxiv.org/abs/2610.30909"><img alt="arXiv: 2610.30909" src="https://img.shields.io/badge/arXiv-2610.30909-b31b1b?style=for-the-badge"></a>
</p>

<p>
<a href="#one-icon-every-os">Start</a> ·
<a href="#watch-it-run">Watch</a> ·
<a href="#what-you-can-do">Features</a> ·
<a href="#ask-in-your-own-words">Ask in words</a> ·
<a href="#simulate-compare-optimize">Simulate</a> ·
<a href="#stores-layouts-and-shelves">Stores</a> ·
<a href="#marketing-studio">Marketing studio</a> ·
<a href="#online-stores">Online stores</a> ·
<a href="#how-it-works">How it works</a> ·
<a href="#validated-on-real-baskets">Validation</a> ·
<a href="#for-developers">Developers</a> ·
<a href="#citation">Citation</a> ·
<a href="#credits">Credits</a> ·
<a href="#license">License</a> ·
<a href="./TwinStore_Technical_Report.pdf">Technical report (PDF)</a> ·
<a href="./QUICKSTART.md">한국어 빠른 시작</a>
</p>

<sub>TwinStore is built on <a href="https://github.com/intellicia-public/parastore">ParaStore</a> by Intellicia (인텔리시아). We gratefully acknowledge their original open-source codebase, released under the MIT License.</sub>

</div>

---

## Why TwinStore

- **A twin, not a mock-up.** Shelf photos become planograms, floor-plan sketches become the store grid, receipts and
  POS exports score the simulation, storefront photos set how many people walk in.
- **Shoppers that look.** Vision-language models look at each shelf the shopper passes — a chart of the shelf with
  names, prices and signs, optionally with the shelf photographed in the 3D store above it, or a real shelf photo in
  Shelf Lab — and say what tempts them. Purchases are seeded draws, so two layouts are always compared on the very
  same people.
- **Answers with error bars.** Paired A/B runs with confidence intervals, a layout optimizer judged by vision shoppers,
  conjoint and concept tests for marketers, compliance audits priced in revenue per day, and a validation loop against
  real households' baskets.
- **Ask the shopper why.** Follow any one shopper's path and thoughts, then interview them — or a whole segment —
  after the day is over.
- **Say it in a sentence.** Describe a test, a layout change, a new store or an optimization goal in your own words;
  TwinStore drafts it on your layout's own products and shelves, and nothing runs until you start it.

## One icon, every OS

Download the archive for your computer from **[Releases](https://github.com/BrainJellyPie/twinstore/releases/latest)**,
unpack it and double-click the **TwinStore** icon. The browser opens a boot screen with live progress and switches to the
app when it is ready. Nothing to install beforehand — the first start fetches Python and the packages (a few minutes,
once); later starts take seconds.

**Updating:** unpack the new version anywhere; your stores come along (they live in your user folder, not the app folder).

> [!NOTE]
> **Windows may say "Windows protected your PC".** That is normal for a new app without a code-signing
> certificate, not a virus warning: click **More info → Run anyway**. On a Mac, open TwinStore once, then
> System Settings → Privacy & Security → **Open Anyway**.

<table>
<tr>
<td width="56%"><img src="./.github/assets/twinstore/media/boot.jpg" alt="TwinStore boot screen"></td>
<td>

| Computer | Download | Double-click |
| :-- | :-- | :-- |
| Windows 10/11 | `…-windows-x64.zip` | **TwinStore.exe** |
| macOS 11+ | `…-macos.zip` | **TwinStore.app** |
| Linux x64 / arm64 | `…-linux-*.tar.gz` | **twinstore** |

Clicking the icon again reopens the running app. **Closing the browser tab does not
stop TwinStore**: when you are done, press **Quit** at the top right of the app (or
<kbd>⌘K</kbd> / <kbd>Ctrl K</kbd> → **Quit TwinStore**).
First-time security prompts and details: [`QUICKSTART.md`](./QUICKSTART.md).

</td>
</tr>
</table>

**No API key is needed to start.** The sample store runs with the rule-based engine, and without a key TwinStore runs a
small model on your own computer for vision shoppers and, once it is ready, for the text features too (slower and
less capable than a cloud model); a key the provider turns down is treated the same way. The default text model is Claude Haiku 5.5 when an Anthropic key is added. For language and vision shoppers, add an OpenAI, Anthropic, Gemini, Qwen or
OpenRouter key — or any OpenAI-compatible server such as vLLM, Ollama or llama.cpp — under **Models**.

**Six languages.** The language control next to the theme switch offers English, 한국어, 中文, 日本語, Español and
Français; it follows your browser on first use and remembers your choice. Home, navigation, the command palette, the
new-store wizard, layouts, templates and the simulation launcher are translated; detailed editors and technical
server messages are still in English.

## Watch it run

<table>
<tr>
<td width="50%"><a href="./.github/assets/twinstore/twinstore-promo.mp4"><img src="./.github/assets/twinstore/twinstore-promo-poster.jpg" alt="TwinStore film"></a><br>
<b>The film</b> · 55 s · what TwinStore is, in motion (<a href="./.github/assets/twinstore/twinstore-promo.mp4">MP4</a>)</td>
<td width="50%"><a href="./.github/assets/twinstore/twinstore-demo.mp4"><img src="./.github/assets/twinstore/twinstore-demo-poster.jpg" alt="TwinStore running"></a><br>
<b>The app, running</b> · 75 s real recording: home, ⌘K palette, 3D playback, heatmap, shopper's eye, one shopper's journey, marketing studio, conjoint, shelf capture, neighborhood, night theme (<a href="./.github/assets/twinstore/twinstore-demo.mp4">MP4</a>)</td>
</tr>
</table>

<details>
<summary><b>Feature demos</b> · short real recordings of single features</summary>

Each preview loops; click it for the full-quality MP4.

<table>
<tr>
<td width="50%"><a href="./.github/assets/twinstore/demos/templates.mp4"><img src="./.github/assets/twinstore/demos/templates.webp" alt="Start from a template"></a><br>
<b>Start from a template</b> · 14 s · pick a store format, then a ready-made floor plan from the gallery (<a href="./.github/assets/twinstore/demos/templates.mp4">MP4</a>)</td>
<td width="50%"><a href="./.github/assets/twinstore/demos/situations.mp4"><img src="./.github/assets/twinstore/demos/situations.webp" alt="Set the scene"></a><br>
<b>Set the scene</b> · 10 s · weekday, weather, holiday and neighborhood visitors before a run (<a href="./.github/assets/twinstore/demos/situations.mp4">MP4</a>)</td>
</tr>
<tr>
<td width="50%"><a href="./.github/assets/twinstore/demos/playback.mp4"><img src="./.github/assets/twinstore/demos/playback.webp" alt="Watch the day"></a><br>
<b>Watch the day</b> · 12 s · 3D playback with the clock, live sales and the heatmap (<a href="./.github/assets/twinstore/demos/playback.mp4">MP4</a>)</td>
<td width="50%"><a href="./.github/assets/twinstore/demos/shopper-eye.mp4"><img src="./.github/assets/twinstore/demos/shopper-eye.webp" alt="Shopper's eye"></a><br>
<b>Shopper's eye</b> · 7 s · ride along at eye level as a shopper walks the aisles (<a href="./.github/assets/twinstore/demos/shopper-eye.mp4">MP4</a>)</td>
</tr>
<tr>
<td width="50%"><a href="./.github/assets/twinstore/demos/journey.mp4"><img src="./.github/assets/twinstore/demos/journey.webp" alt="One shopper's journey"></a><br>
<b>One shopper's journey</b> · 15 s · follow a single shopper: route, stops, what they saw and bought (<a href="./.github/assets/twinstore/demos/journey.mp4">MP4</a>)</td>
<td width="50%"><a href="./.github/assets/twinstore/demos/compare.mp4"><img src="./.github/assets/twinstore/demos/compare.webp" alt="Compare two runs"></a><br>
<b>Compare two runs</b> · 13 s · the same shoppers in two layouts, side by side (<a href="./.github/assets/twinstore/demos/compare.mp4">MP4</a>)</td>
</tr>
<tr>
<td width="50%"><a href="./.github/assets/twinstore/demos/optimize.mp4"><img src="./.github/assets/twinstore/demos/optimize.webp" alt="Optimize the layout"></a><br>
<b>Optimize the layout</b> · 14 s · let TwinStore search for a better arrangement toward your goal (<a href="./.github/assets/twinstore/demos/optimize.mp4">MP4</a>)</td>
<td width="50%"><a href="./.github/assets/twinstore/demos/ab-test.mp4"><img src="./.github/assets/twinstore/demos/ab-test.webp" alt="A/B test a price"></a><br>
<b>A/B test a price</b> · 8 s · a discount tested on paired shoppers, by segment (<a href="./.github/assets/twinstore/demos/ab-test.mp4">MP4</a>)</td>
</tr>
<tr>
<td width="50%"><a href="./.github/assets/twinstore/demos/conjoint.mp4"><img src="./.github/assets/twinstore/demos/conjoint.webp" alt="Conjoint study"></a><br>
<b>Conjoint study</b> · 8 s · design a choice study, run it, read part-worths and willingness to pay (<a href="./.github/assets/twinstore/demos/conjoint.mp4">MP4</a>)</td>
<td width="50%"><a href="./.github/assets/twinstore/demos/shelflab.mp4"><img src="./.github/assets/twinstore/demos/shelflab.webp" alt="Shelf lab"></a><br>
<b>Shelf lab</b> · 8 s · lay out a shelf and generate new packs for it (<a href="./.github/assets/twinstore/demos/shelflab.mp4">MP4</a>)</td>
</tr>
<tr>
<td width="50%"><a href="./.github/assets/twinstore/demos/shelftest.mp4"><img src="./.github/assets/twinstore/demos/shelftest.webp" alt="Shelf test"></a><br>
<b>Shelf test</b> · 9 s · place a new pack on the shelf and see whether shoppers notice it (<a href="./.github/assets/twinstore/demos/shelftest.mp4">MP4</a>)</td>
<td width="50%"><a href="./.github/assets/twinstore/demos/neighborhood.mp4"><img src="./.github/assets/twinstore/demos/neighborhood.webp" alt="The neighborhood"></a><br>
<b>The neighborhood</b> · 6 s · the store in its catchment: homes, rivals and who walks in (<a href="./.github/assets/twinstore/demos/neighborhood.mp4">MP4</a>)</td>
</tr>
</table>

</details>

## What you can do

<table>
<tr>
<td width="50%"><img src="./.github/assets/twinstore/screens/floor-light.jpg" alt="Photoreal 3D store with photographic shoppers"><br>
<b>Photoreal 3D twin.</b> Photographic shoppers walk the floor on a wall-clock day; scrub, pause, speed up, follow anyone. <b>Photo</b> path-traces any view into a still.</td>
<td width="50%"><img src="./.github/assets/twinstore/screens/shopper-light.jpg" alt="Shopper's-eye view"><br>
<b>Shopper's-eye view.</b> The first-person camera walks the aisles at a shopper's eye height.</td>
</tr>
<tr>
<td><img src="./.github/assets/twinstore/screens/heat-light.jpg" alt="Footfall heatmap"><br>
<b>Heat, dwell and traffic.</b> Footfall, dwell and predicted-traffic layers, rack KPIs in 3D, revenue by rack.</td>
<td><img src="./.github/assets/twinstore/screens/shoppers-light.jpg" alt="One shopper's journey with thoughts"><br>
<b>Follow one shopper, then ask why.</b> Their path, stops, the shelf they saw and their thoughts step by step; interview them afterwards, alone or as a group.</td>
</tr>
<tr>
<td><img src="./.github/assets/twinstore/screens/run-light.jpg" alt="Run a simulation: engine, model, situation"><br>
<b>Run a day.</b> Rule, language or vision shoppers; one model or an ensemble; 19 situations from a rainy Monday to a big match.</td>
<td><img src="./.github/assets/twinstore/screens/optimize-light.jpg" alt="Layout optimizer"><br>
<b>Optimize the layout.</b> Search shelf placements or rack positions for revenue, conversion or shorter walks, judged by vision shoppers.</td>
</tr>
<tr>
<td><img src="./.github/assets/twinstore/screens/market-ab-light.jpg" alt="Marketing studio: A/B test result"><br>
<b>A/B tests for marketers.</b> Price, discount, promotion sign, placement or a new pack, on the same shoppers; lifts with 95 % CIs, by segment, with a report.</td>
<td><img src="./.github/assets/twinstore/screens/market-conjoint-light.jpg" alt="Marketing studio: conjoint study builder"><br>
<b>Conjoint studies.</b> Which features and prices win the choice: part-worths, importance, willingness to pay and a market simulator.</td>
</tr>
<tr>
<td><img src="./.github/assets/twinstore/screens/market-concept-light.jpg" alt="Marketing studio: concept test builder"><br>
<b>Concept tests.</b> Drop pack images; personas rate intent, appeal, value, price range and preference.</td>
<td><img src="./.github/assets/twinstore/screens/market-sweep-light.jpg" alt="Price sweep: demand curve"><br>
<b>Price sweeps.</b> A product at five prices on the same shoppers: demand curve, elasticity, revenue-maximising price.</td>
</tr>
<tr>
<td><img src="./.github/assets/twinstore/screens/capture-light.jpg" alt="Shelf capture and Shelf Lab"><br>
<b>Shelf capture &amp; Shelf Lab.</b> A phone photo becomes a planogram; edit it counterfactually, audit it and plan the restock.</td>
<td><img src="./.github/assets/twinstore/screens/town-light.jpg" alt="Neighborhood demand"><br>
<b>The neighborhood.</b> Generated or OpenStreetMap towns, Huff demand, rival stores, synergy with the shop next door.</td>
</tr>
<tr>
<td><img src="./.github/assets/twinstore/screens/wizard-light.jpg" alt="New store wizard with a starting layout"><br>
<b>New store in two steps.</b> Store details, address, hours and one of 82 furnished starting layouts — or a floor-plan image.</td>
<td><img src="./.github/assets/twinstore/screens/home-dark.jpg" alt="Home, night theme"><br>
<b>Day and night.</b> A command bar, <kbd>⌘K</kbd> palette for everything, quick links on every store, light and dark themes.</td>
</tr>
</table>

## Ask in your own words

Most set-up screens take a sentence. The text model drafts the settings from it, and TwinStore checks every draft
against your data: products, shelves and images the layout or library does not have are reported, never invented; an
ambiguous name is not guessed; and nothing runs until you press start.

| Where | You write | You get |
| :-- | :-- | :-- |
| Command palette (<kbd>⌘K</kbd> / <kbd>Ctrl K</kbd>) inside a store | "would a 1+1 sign on cola sell more than a 20 % cut?" | the right page, with the draft filled in: an A/B, shelf, concept or conjoint test, a staff script, the neighborhood, a question about the run, a shopper search or the optimizer |
| A/B, shelf, concept and conjoint builders | the question the test should answer | variants, the product under test, the images and questions to show, or attributes and price levels |
| Staff scripts | a direction ("lead with value") | an alternative script B built only from the verified facts given |
| New store | "a campus convenience store at the university gate, open weekdays 7 to 23" | name, type, hours, starting format and currency, then a customer profile |
| Add layout → **Additional design brief** | "bright, two tills by the door, no tobacco" | the generator's options; whatever no option can express is listed |
| Store → Layout → **Change it in words** | "green tea at eye level and 10 % off all ice cream" | the edits applied to a copy, saved as a new layout when you keep them |
| Run dialog → **Describe the day** | "rainy Friday evening, the game next door at 7, out of ice cream" | weather, weekday, event, promotions and stock-outs |
| Area | "a busy campus street, two rival stores nearby" | the town generator's settings |
| Run results → **Ask about this run** | "which shelf converts worst, and why?" | an answer with the figures it rests on, and follow-up questions; **Explain the difference** does the same for two compared runs |
| Shoppers tab | "women in their 20s who stopped at the ice cream freezers but bought nothing" | exactly the shoppers who match, read from the run's records, ready for a group interview |
| Optimize | "more impulse sales, keep the fridges where they are, at most 6 changes" | objective, scope, move limit and locked shelves |
| Group interview or analyst → **Turn this into tests** | | up to three test questions, each opening a drafted test |

What shoppers say stays a hypothesis until a test runs. Without a key for the app's text model, these helpers fall
back to a fast model of a provider that has one; simulation runs and studies keep the model you chose.

## Simulate, compare, optimize

The **Floor** page is the store's day. **Run simulation** asks:

- **Who shops.** The rule-based engine (seconds, no model), language-model shoppers that plan, intend and give in to
  impulses, or vision shoppers that look at the shelves they pass.
- **What a vision shopper sees at a shelf.** **Chart**: a flat drawing of the shelf with names, prices and numbers.
  **Chart + 3D photo**: the same chart with the shelf photographed in the 3D store above it, tagged with the same
  numbers: closer to what a shopper sees, about twice the image per call. The browser photographs each shelf once
  before the run (only shelves changed since are photographed again); a shelf changed by the day's promotions or
  stock-outs is shown as the chart.
- **Which model.** The app default, one model, or an ensemble that mixes models across shoppers or lets them vote. The
  dialog estimates the number of model calls before you start.
- **One store, shared.** By default the day's shoppers share the shelves and the tills: stock runs out as they take
  it and staff refill it, a sold-out product is replaced from the same shelf or the sale is lost, and shoppers queue
  for a free till, some leaving their basket when the wait runs past their patience. **Store operations** in the
  results prices the empty shelves, shows the wait by hour and how many tills each hour needed. The model calls are
  the same as without it. **Try other stock and staffing** replays any finished run's shoppers under other stock,
  refills and hourly tills in seconds, and with your costs finds the plan that leaves the most.
- **What kind of day.** One of **19 situations** (weather, weekday or holiday, crowding, local events, promotions,
  sold-out items) or your own, plus customer sample, seed and preview-or-final. Vision runs start with at most 30
  customers and language-model runs with at most 300.

**Results** fill in as the day plays: revenue, conversion, basket, footfall and dwell heatmaps, revenue by rack, what
caught the vision shoppers' eye and at which shelf level, who walked in, and run diagnostics (failed customers,
dropped over-budget or hallucinated buys, cost). Export every customer as CSV, validate a run against your POS export
(CSV or XLSX) or receipts, and compare observed movement tracks with simulated occupancy.

- **Compare runs** — two runs side by side on paired customers: differences with bootstrap 95 % intervals, P(B > A)
  and the sample needed to detect a 5 % change.
- **Optimize** — choose a goal (revenue, conversion, units, impulse revenue or shorter walks), what may change
  (shelves, rack positions or both) and a search method (hill climbing, simulated annealing or a genetic algorithm).
  A rule model calibrated to the vision shoppers searches; an optional vision panel judges the finalists with
  P(better). The winner is saved as a new layout.

### Shoppers and interviews

The **Shoppers** tab lists everyone who came, sorted by spend, empty-handed visits, impulse buys or visit length. Open
one to see their path, every stop, the shelf face they saw and what they thought; **Follow in 3D** keeps the camera
on them. Then ask them anything ("why didn't you buy anything at the snack shelf?"): answers come from their persona
and trip only and point at the steps they mean. A **group interview** asks a segment (4–40 shoppers) one question and
codes the answers into themes.

### Photo mode

**Photo** path-traces the current view (three-gpu-pathtracer) into a photoreal still with global illumination,
area-light shadows, glossy floors, glass and HDR store lighting: 64, 256 or 1,024 samples, denoising and depth of
field (f/1.4–5.6) in the shopper's view, saved as PNG.

## Stores, layouts and shelves

### Store formats and templates

Start from **82 furnished formats** — convenience stores, supermarkets, hypermarkets, pharmacies, cafés, bakeries,
restaurants of many cuisines, fashion, electronics, bookstores, pet and garden stores, airport and station retail,
weekend markets and more, each with its own assortment, palette, seating and checkouts — or from **25 multi-floor
buildings** (department store, dining house, campus hub and more). Choose the categories to stock, where the entrance,
exit and checkouts go, dining tables, aisle widths, shelf direction, areas to keep clear, opening hours per weekday
and colors; download the plan as SVG. Every option and the floor editor (up to 40×40 cells) are documented in
[`STORE_TEMPLATES.md`](./STORE_TEMPLATES.md).

The new-store wizard asks for a format, size and currency, then your customers (optionally with a CSV or XLSX of up to
10 MB) and generates personas with the configured model. Alternatives of a store live side by side as layout tabs.
Automatic starter products are enabled by default when a model is configured: the text model selects existing
catalog products for the store category before creation. Without a model, the wizard starts with the format's
stocked assortment. You can also turn automatic selection off to use that assortment. Model-selection failures
create no partial store. The catalog includes 1,784 products in 155 categories and 1,312 locally bundled product images.
All 82 map templates also stock these products directly in their format defaults, with departments matched to
the store: baby supplies and toys, pharmacy care, coffee equipment, homeware, pet supplies and more.
Together, the default maps cover the full catalog. Previews and saved floors retain the same products and images.

### Stock and edit a layout

- **Auto-place starter products** (Step 2) uses the text model to choose existing catalog products for the store
  category, previews their placement on empty racks and saves a separate stocked
  layout; existing products and geometry stay as they are. Reference products and prices are examples, not your
  stock. [Guide](./USAGE.md#fill-existing-empty-shelves-with-starter-products).
- **Reuse shelf products** (Step 2) copies a finished shelf’s reviewed assortment to compatible empty racks,
  preserving exact product values and saving a separate layout. [Guide](./USAGE.md#reuse-a-finished-shelf-assortment).
- **Use library photos** (Step 2) reuses uploaded packshots on exact SKUs, reviews before/after images
  and saves a separate layout with retained photo copies. [Guide](./USAGE.md#reuse-uploaded-product-photos-on-a-layout).
- **Edit products together** (Step 2) changes names, prices and promotion text of selected products with a
  before/after preview and saves a separate layout. [Guide](./USAGE.md#edit-placed-products-together-without-a-spreadsheet).
- **Change it in words** applies price, discount, sign and placement edits from a sentence (see
  [Ask in your own words](#ask-in-your-own-words)).
- **Excel round trip** — download the planogram as a workbook, edit it and upload it back.

### Shelf capture and Shelf Lab

A phone photo of a shelf becomes a rack face in the planogram. **Add photos** takes several files at once, checks
duplicates and processes them one at a time, with pause and per-photo retry
([queue details](./USAGE.md#upload-several-shelf-photos-with-a-controlled-queue)). **Save queue on this browser**
keeps original photos and upload settings for paused recovery after a browser restart;
[recovery details](./USAGE.md#save-a-photo-queue-and-resume-later). **Combine reviewed shelf photos**
previews completed photos together and saves them as one new draft layout without extra model calls
([workflow](./USAGE.md#combine-reviewed-shelf-photos-into-one-layout)).

**Save queue on this browser** retains selected photos and settings for a paused restore after reload.
Browser storage can be cleared or evicted and is not a backup. Combining keeps original layouts and photos;
missing products block saving and reduced facing counts need confirmation.

**Shelf Lab** edits real shelf photos counterfactually (Fig. 3 below) and audits them against the reference layout.
Completed audits rank missing products by net contribution (**Restocking priorities**) and turn verified stockroom
counts, pack sizes and costs into a budgeted restock worksheet in whole supplier packs, without placing orders or
predicting recovered sales. Details: [`SHELF_LAB.md`](./SHELF_LAB.md).

### The neighborhood

**Area** puts the store in a town: generate one (residential, university, station, suburban, tourist or mixed, at a
chosen density) or import streets and venues from OpenStreetMap. A Huff demand model gives visitors per day, market
share, catchment, average walk, visitors by hour and who comes; open or close a venue to see what changes, and let
runs draw their visitors from the town. A storefront photo sets how strongly the store pulls, a rival's shelf photo
sets its price index, and a vision check rates the synergy with the shop next door.

## Marketing studio

For brand managers, category teams, store operators and research agencies (**Market** in the command bar). Synthetic
respondents are for screening and direction; calibrate against a real panel before deciding.

| Tab | What it answers |
| :-- | :-- |
| **A/B tests** | Price, discount, promotion sign, placement, new pack or category re-price against the control, on the same shoppers with the same random numbers. Paired differences with bootstrap 95 % intervals, by age group and gender; a winner only when its interval clears zero. Recipes include a **price sweep** (demand curve, elasticity, revenue-maximising price); a **price × sign** analysis splits control, price-only, sign-only and combined arms into main effects and the interaction. |
| **Shelf tests** | The same respondents see the shelf as it is and with a new pack, price or sign: pick share and what caught the eye first. |
| **Concept tests** | Up to four images rated by sampled personas with age and gender quotas: purchase intent, appeal, value, stand-out, a Van Westendorp price range and preference. |
| **Conjoint** | Choice-based conjoint: part-worths, attribute importance and willingness to pay from a multinomial logit, importance by segment, and a market simulator with price sliders. |
| **Staff scripts** | Two greetings, recommendations or objection-handling lines on the same synthetic shoppers: purchase intent, trust and pressure, with paired intervals. A screen for wording, not a sales forecast. |
| **Field pilots** | A staff-script test turned into a balanced assignment sheet for real shifts: sample size and duration, observed encounters and POS purchases, a conservative 95 % conversion interval, plus staff/shift sensitivity, cost scenarios and observed staff time. |
| **Price checks** | Shelf-label and checkout observations reconciled by check ID, with signed differences by currency. |
| **Protocols** | Research plans and reasoned amendments with complete snapshots and exports. |
| **Unit prices** | Competitor offers compared across pack sizes, with date, stock and purchase-condition exclusions. |
| **Inventory** | Observed stock, movements, sales and costs reconciled per SKU into sell-through, turnover and GMROI. |
| **Products** | Packshots or phone photos of packs (background cut out, named from what the pack says), linked to the shelf products they replace. |

Finished A/B, shelf, concept and conjoint tests have print-ready reports and can be duplicated into the next one.
**Read the answers** on concept, shelf, conjoint and staff-script results groups respondents' reasons into themes and
writes a short commentary on the numbers, labelled as model-written.

## Online stores

**Online** in the command bar builds web shops for a store and sends virtual shoppers through them the way people
use a browser. Start from 42 ready-made shops — groceries, quick commerce, pharmacy, beauty, fashion, electronics,
pets, toys, food delivery, a marketplace, flash sales and more, about 2,500 listings, most with photos — or put a
layout's own shelves online, then change what a designer would: layout, search quality, sponsored listings, urgency
and social proof, popups, cookie banners, delivery fees, coupons, guest checkout, checkout steps, payment methods,
last-step fees, pre-ticked add-ons, returns and page speed — run ad campaigns for its products and send cart
reminder emails.

Each page is a screenshot with a numbered badge on every clickable element. A **vision model** looks at it and picks
one option — search (and what to type), go back, open product 3, open the menu or settings, add a payment method,
close the tab; a **text model** reads the page outline instead; **rule shoppers** run instantly. Shoppers come with a
mission (buy something, window-shop, compare, hunt bargains, find a gift, reorder), a device, a budget, patience,
comfort with websites and eyesight (low vision, colour blindness and older eyes see filtered screenshots). You can
browse any store yourself by clicking the same screenshot.

| Result | What it shows |
| :-- | :-- |
| **Variants on the same shoppers** | Up to four stores per run; conversion, revenue per visit, add-to-cart, clicks and time as paired differences with bootstrap 95 % intervals. |
| **Funnel and exits** | Visit → product → cart → checkout → payment → order, and the pages people left from. |
| **Ads** | Banners, sponsored tiles and listings, product-page and cart ads, popups: impressions, clicks, credited orders and ROAS per ad, and against the same store without it the extra units, revenue and incremental ROAS. |
| **Cart reminders** | Emails to shoppers who left a cart, optionally with a discount: who came back, recovered orders and revenue, the discount given. |
| **Friction audit** | Popup exits, forced sign-in, last-step fees, add-ons paid without unticking, failed coupons, empty searches, sold-out pages, slow exits. |
| **Exit survey** | Satisfaction, ease, NPS, return intent and the biggest annoyance, from model shoppers right after the visit. |
| **Search, products, clicks** | What people searched for (and found nothing), product views/adds/sales, a click map of the screenshots. |
| **Replays and data** | Every visit page by page with the shopper's thoughts, and a conversation with the shopper about it; segments by mission, device, age, gender and eyesight; a clickstream CSV. |

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
layout are priced in revenue per day by paired simulation.

### Photos in, twin out

| Input | What TwinStore does with it |
| :-- | :-- |
| Shelf photo | detects shelves and facings, reads names and price tags → a rack face in the planogram |
| Floor-plan image or multi-page PDF | page and rotation preview → ink mask or vision model → walls, racks and doors on an 8–16 tile grid |
| Storefront photo | a vision model rates sign, entrance, window and upkeep → the venue's pull in the neighborhood model |
| Receipt photos | transcribed by a vision model, matches reviewed → corrected POS lines that score a run |
| POS export with timestamps | sets when the simulated shoppers arrive, and scores a run's sales |
| Anonymous track CSV | observed vs simulated visitor and occupancy heatmaps, with tracking gaps accounted for |
| Rival's shelf photo | price index and assortment overlap against your layout → the rival's price-adjusted pull |

## Validated on real baskets

<img src="./.github/assets/twinstore/validation.png" alt="Fig. 4 — Evidence that the twin's shoppers shop like real ones, on held-out households of public datasets">

**Fig. 4 — Validation.** TwinStore's own engines shop for the households of public datasets, and the simulated
trips are compared with real trips they never saw. The main test uses dunnhumby's *The Complete Journey*: 150
households and 14 weeks, held out (replicated on a second panel), with Claude Haiku 5.5, Qwen 3.8 Flash and GPT-6
Luna as decision models, alone and mixed into one population. Every failure the data exposed changed the simulator:
visit times and trip size, silent fallbacks, shelf prices and price response, walking speed and time at the shelf,
repeated staples and habits within a category, and situation effects measured on real receipts.

| Check (held out) | Simulated | Real reference |
| :--- | :--- | :--- |
| Category mix of the population (JSD) | `0.009–0.018` (two panels) | `0.006–0.012` (a household's own earlier receipts) |
| Per-household hit vs the store's best-sellers | `+0.027 to +0.035` (95 % CIs above 0) | – |
| Demographic differences in category mix, told only who the household is | `r 0.27` (p 0.006) | `0.30` (one own earlier receipt) |
| Repeat purchases (share of a trip's products bought before) | `0.56–0.72` | `0.73` |
| Classifier AUC, real vs simulated receipt | `0.55–0.62` | `0.46–0.52` (own earlier receipt vs later one) |
| Own-price elasticity | `−0.78 to −1.60` | `−0.70` (M5) to `−2.62` (meta-analysis) |
| Situation effects (weekend, match, seasons, holidays), correlation with real | `0.80–0.89` | ignoring them: error `0.109`, simulated `0.046–0.111` |
| Evening vs morning: beer, ice cream | `1.4–2.2×`, `1.3–1.8×` | `2.1×`, `1.9×` |
| Bigger trips from farther away (Ta-Feng) | `1.25–1.36×` | `1.33×` |
| Walking speed (13,159 tracks) | `1.12 m/s` | `1.13 m/s` |
| Seconds at the shelf per unplanned purchase (eye tracking) | `7–9` (median) | `8.2` |

The full validation study (what failed, what was fixed, its limits and how to reproduce it) is maintained outside
this repository; every number in it is recomputed from the saved trips.

## For researchers

Every stimulus and every model call is seeded and cached, so experiments are paired and reproducible, and figures
regenerate from saved JSON without model calls. TwinStore is built for:

- **VLM shopper bench** — position and order biases (Latin-square placement, shuffled tag numbers), merchandising
  levers, price read-back, persona and situation conditioning, corruption robustness, image-vs-text ablation, agreement
  across models (Fleiss' κ).
- **Shelf-to-planogram digital twins** — detection + VLM reading with exact ground truth, and *decision-preserving
  reconstruction*: does the simulator reach the same conclusion on the reconstruction as on the original?
- **Sim2real for shopper agents** — the same panel on renders, tagged photos and raw photos (Shelf Lab).
- **Expensive-oracle layout optimization** — a rule-based surrogate proposes, vision shoppers judge on a paired panel.
- **Synthetic respondents** — concept tests, shelf tests and choice-based conjoint on persona panels, with
  respondent-level data exported for comparison with human panels.

`uv run python -m store_emulator.lab_cli bench` writes a counterfactual benchmark (`index.jsonl` with images, masks and
edits) from rendered shelves or real captures.

## For developers

<img src="./.github/assets/twinstore/launcher.png" alt="Fig. 5 — One-click launcher">

**Fig. 5 — Launcher.** One Go source builds `TwinStore.exe`, `TwinStore.app` and `twinstore`. It fetches uv if needed,
starts the server on a private port, shows the boot screen at `127.0.0.1:8000` and then proxies the app at that same
address. See [`launcher/README.md`](./launcher/README.md).

```bash
git clone https://github.com/BrainJellyPie/twinstore && cd twinstore
cp backend/.env.example backend/.env   # add an LLM API key if you want LLM shoppers — never commit real keys
./scripts/dev.sh                       # backend on :8000, frontend on :5173
```

Requirements: Python **3.13+** with [uv](https://github.com/astral-sh/uv), Node **20+** with **pnpm 10.33.0**. The
optional Grounding DINO detector for shelf capture: `cd backend && uv sync --extra capture` (pulls PyTorch).
Contributor and AI-agent conventions: [`AGENTS.md`](./AGENTS.md). Running TwinStore with an AI assistant: point it at
[`USAGE.md`](./USAGE.md). History: [`CHANGELOG.md`](./CHANGELOG.md).

<details>
<summary><b>Run each side, build, verify</b></summary>

```bash
cd backend && uv sync && uv run uvicorn store_emulator.server.main:app --reload   # API docs at :8000/docs
cd frontend && pnpm install && pnpm dev                                          # VITE_API_URL=… to point elsewhere
cd frontend && pnpm build                                                         # the backend serves frontend/dist
launcher/build.sh                                                                 # TwinStore.exe / .app / linux → launcher/dist
```

Verification (keep all green): `uv run pyright src/` and `uv run pytest` in `backend`; `pnpm build`, `pnpm lint` and
`pnpm test` in `frontend`.

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

The former command name `parastore` still works. Everything in the app is also an HTTP API (`:8000/docs`).

</details>

<details>
<summary><b>Vision shoppers without an API key</b></summary>

With no API key set, TwinStore says so under the command bar and runs its vision shoppers on a small open model on your
computer, picked from the hardware:
- a GPU gets Qwen3.5-9B, 4B or 2B (CUDA on NVIDIA, Metal on Apple silicon, Vulkan on AMD/Intel);
- a CPU gets Qwen3.5-2B, 0.8B or LFM2.5-VL-450M, by cores and free memory.

It downloads the matching [llama.cpp](https://github.com/ggml-org/llama.cpp) build and the model into
`.data/local_vlm/` and serves it on 127.0.0.1. Opened from the app icon this happens by itself; otherwise press
**Start local model** in the notice or on the Models page. A llama.cpp server already running on port 8081 is used
as it is.

| Variable | Effect |
| :--- | :--- |
| `TWINSTORE_LOCAL_VLM=off` | turns it off |
| `TWINSTORE_LLAMA_SERVER=/path/to/llama-server` | uses your own build |
| `TWINSTORE_LOCAL_VLM_MODEL` | forces a model: `qwen3.5-0.8b`, `qwen3.5-2b`, … |

To run the model by hand:

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

Both favor products in the top row of a shelf image (2B: ~70% of picks). A cloud key gives faster and far more
accurate shoppers; treat small-model picks as a model to calibrate, not as ground truth.

</details>

<details>
<summary><b>Models and configuration</b></summary>

**Models** lists OpenAI, Anthropic, Gemini, Qwen and OpenRouter, plus any custom OpenAI-compatible endpoint (vLLM,
Ollama, llama.cpp, a gateway). Keys stay on your computer; each provider can be tested with one click and given its own
default model. Runs and the optimizer can use the app default, a specific model or an ensemble; the marketing studio
uses the app default or a model you pick per test.

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
| `PARASTORE_DATA_HOME` | folder that holds `.data` (stores, runs, settings, the local model). The app icon and the fallback scripts default to the per-user TwinStore folder (`%LOCALAPPDATA%\TwinStore`, `~/Library/Application Support/TwinStore`, `~/.local/share/twinstore`); the backend run on its own to `backend/` |

</details>

## Limitations

- **Calibrate before you trust numbers.** Out of the box the shoppers are plausible, not fitted to your store. Use the
  fidelity report against your POS data, read paired differences with their intervals, and see the validation loop for
  what calibration involves.
- **Synthetic respondents are not a panel.** Concept, shelf, conjoint and staff-script results screen ideas; confirm
  with real people before pricing or launching on them.
- **Model calls cost money and time.** A week of personas is every estimated visitor (up to 1,000 a day), which can be
  hundreds of calls; the app times one call first and asks before writing them all when that takes about 10 minutes or
  costs about $1, offering a quick sample instead. Model-based runs ask the same way. The rule-based engine and
  response caches make iteration free.
- **Online shoppers are a screen, not a forecast.** Rule shoppers follow illustrative, uncalibrated probabilities;
  model shoppers react to what each page shows but are not real traffic. Compare variants on the same shoppers
  rather than reading absolute conversion rates.
- **One store at a time.** No fleet view or multi-week dynamics; crowding is light (per-shopper paths, no queues);
  floors of a building are simulated separately.
- **APIs and data shapes may still change** between versions.

## Citation

If you use TwinStore in your research, please cite:

Minhyeok Lee. **TwinStore: A Synthetic Consumer Platform Using Vision–Language Models.**
arXiv:2610.30909, 2026. [Paper](https://arxiv.org/abs/2610.30909) ·
[DOI: 10.48550/arXiv.2610.30909](https://doi.org/10.48550/arXiv.2610.30909).

```bibtex
@misc{lee2026twinstore,
  title         = {{TwinStore}: A Synthetic Consumer Platform Using Vision--Language Models},
  author        = {Minhyeok Lee},
  year          = {2026},
  eprint        = {2610.30909},
  archivePrefix = {arXiv},
  primaryClass  = {cs.AI},
  doi           = {10.48550/arXiv.2610.30909},
  url           = {https://arxiv.org/abs/2610.30909}
}
```

## License

**TwinStore License 1.0** — see [`LICENSE`](./LICENSE).

| Who | Allowed |
| :-- | :-- |
| Research (academic or in a company, not in production) and non-commercial use | ✅ free, unlimited |
| Commercial use by individuals and organizations with annual revenue up to **US$1M** | ✅ free |
| Everyone else | 📩 separate license — [open an issue](https://github.com/BrainJellyPie/twinstore/issues) |

TwinStore is built on ParaStore © 2026 intellicia, whose code remains available under the MIT License; its notice is
kept in full in [`LICENSE`](./LICENSE). Dependencies keep their own licenses
([`LICENSES-BACKEND.md`](./LICENSES-BACKEND.md), [`LICENSES-FRONTEND.txt`](./LICENSES-FRONTEND.txt)).

## Credits

- **Foundation: ParaStore by Intellicia (인텔리시아).** TwinStore builds on
  [ParaStore](https://github.com/intellicia-public/parastore). We acknowledge Intellicia and the ParaStore contributors
  for creating and sharing the original open-source codebase that forms TwinStore's foundation. The original
  copyright and MIT License notice are preserved in [`LICENSE`](./LICENSE).
- **Shoppers.** [Microsoft Rocketbox](https://github.com/microsoft/Microsoft-Rocketbox) avatars (MIT), bundled
  locally: fourteen appearances with retargeted standing, walking and browsing animations. Sources and conversion:
  [`frontend/public/assets/people/`](./frontend/public/assets/people/README.md).
- **Materials and lighting.** CC0 scans from [Poly Haven](https://polyhaven.com/) (ceramic flooring, wood fixtures,
  storefront pavement and the [Gear Store HDR panorama](https://polyhaven.com/a/gear_store)) and
  [ambientCG](https://ambientcg.com/) (Plaster 001, Metal 032, Office Ceiling 001, Marble 012), loaded locally with
  procedural fallbacks. Authors, source URLs and checksums: [`materials/`](./frontend/public/assets/materials/LICENSE.txt),
  [`environments/`](./frontend/public/assets/environments/LICENSE.txt).
- **Props, produce and products.** CC0 Poly Haven scans by Rico Cilliers, Alexander Shulha, Oliver Harries, Kuutti
  Siitonen, Jan Martens, Amal Kumar, Dario Barresi, Greg Zaal and Charles Nderitu
  ([`props/`](./frontend/public/assets/props/README.md), [`produce/`](./frontend/public/assets/produce/README.md),
  [`products/`](./frontend/public/assets/products/README.md)).
- **Your own photos.** Uploaded SKU photos and Capture crops appear on 3D packages (round packages use the front
  photo's central label band, an approximation rather than a full scan).
- **Classic view.** Market, character and ghost assets from [Kenney](https://kenney.nl), CC0 1.0 —
  [Mini Market](https://kenney.nl/assets/mini-market), [Mini Characters](https://kenney.nl/assets/mini-characters),
  [Graveyard Kit](https://kenney.nl/assets/graveyard-kit).
- **Data.** Validation uses dunnhumby *The Complete Journey* and *Breakfast at the Frat*, X5 RetailHero, Ta-Feng,
  Instacart, Favorita, M5, Rossmann, Walmart's sales in stormy weather, a supermarket eye-tracking study and the ATC
  pedestrian tracks; the capture benchmark's real-photo check uses ShelfWise "SKUs on shelves PL" (CC BY 4.0). None of
  these datasets are redistributed here.
- **Figures and films.** Generated from HTML in [`.github/assets/src`](./.github/assets/src) (`render.mjs`,
  `render-video.mjs`); the app recording is a scripted Playwright session of the real app.

## Contributing

Issues and pull requests are welcome. Please keep changes focused, run the verification commands above, and follow
[`AGENTS.md`](./AGENTS.md). For commercial licensing, open an issue and we will reach out.
