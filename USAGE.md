# USAGE.md — TwinStore

Operational guide for AI coding assistants (Claude Code, Cursor, Codex,
Aider, …) helping an **end user** run the parastore app — set up a store,
generate personas, and run simulations. This is intentionally separate from
[`AGENTS.md`](./AGENTS.md), which targets contributors modifying the code.

> **For the assistant reading this**: the data-entry step is where most
> runs go wrong, and most failures are silent — vague inputs produce
> generic-looking personas without raising any error. Coach the user
> through the inputs *before* triggering a simulation; once LLM calls
> start, the bill is already running and the only undo is "start over."

## Pipeline mental model

The wizard collects two screens of input, then kicks off an async pipeline. With a furnished template,
automatic starter products are enabled by default: two text-model calls choose categories and exact products
from the bundled catalog before project files or persona jobs are created. These calls are additional to the
pipeline below. Turn off automatic products in Step 1 to use format defaults without these two calls. Empty
layouts do not call the product-selection model. A model-selection failure preserves the form for retry and
creates no partial project.

```
Step 1: Store info  ──┐
Step 2: Customer +    ├──► (optional) supplemental file → LLM summary  (1–2 calls)
        supplement    │         │
                      │         ▼
                      └──► location analysis                            (1 call)
                                │
                                ▼
                           daily-traffic estimate per open day          (N_open_days calls)
                                │
                                ▼
                           persona batch generation                     (≈ visitors / 10 calls)
                                │
                                ▼
                           simulation per persona                       (2–3 calls each)
```

Steps below cover each input in turn.

## Inspect and export a floor plan

In **Add layout → Generate a store from a template**, open **Expand floor plan** to zoom, inspect
coordinates and reserved areas, or download an SVG. **Compare with default** shows the format's
starting plan alongside the current options at the same cell scale. Closing either preview returns
to the current creation form without saving or submitting it.

Preview controls, gate legends, comparison details, numbers, hours and SVG metadata use the selected
interface language (English, Korean, Chinese, Japanese, Spanish or French). A language change keeps
an already expanded preview and its zoom. Store/product names and custom rack/area labels stay as
entered. The SVG always contains the complete floor geometry, independent of the current zoom.
These actions do not run shoppers or call a model. Detailed template-setting coverage is still being
expanded; see `verification/2026-10-22-i18n-coverage.md` for the verified scope.

## Reuse template hours and product settings

Under **Customize layout**, choose opening days and hours, optionally setting each day separately.
Use 0–24 for a full day; closing must follow opening, without crossing into the next day. Keep at
least one open day. Select the product categories and optionally limit each to 1–16 distinct
products. A blank limit uses the full available assortment; individual category limits override
the general limit. These are product types, not inventory quantities. Changing the assortment seed
selects another reproducible mix while keeping the same seed and settings reproduces the selection.

**Export options** downloads the generation settings and design brief as JSON. **Import options**
checks that file before replacing the current settings. The building equivalents include the floor
order and names; they check all floors before replacing the floor list. Manual fixture/product edits
are not included. Source project/layout links and the current layout name are not copied by a
single-floor export. Exact integer seeds and category identifiers stay unchanged in every language.

Hours, category labels, validation, import/export guidance and accessible control names use the
selected interface language. Switching language preserves unsaved values and does not trigger a new
preview request. Known catalog categories are translated; custom/unknown labels remain as supplied.

## LLM call count (static analysis)

Counted directly from the code, not measured.

```
generation_calls = 1                                          # location analysis
                 + N_open_days                                # daily traffic, one per open day
                 + ceil(total_estimated_visitors / 10)        # persona batches, batch_size=10
                 + (2 if supplemental_file_uploaded else 0)   # column-pick + summary

simulation_calls = N_simulated × 3                            # stage1 + stage2 + stage3
                 # stage3 (impulse) is skipped when no products lie on the persona's path,
                 # so the effective multiplier ranges from 2 to 3.
                 # N_simulated = N_personas, or the run's `max_customers` sample.
                 # engine_type="rule_based" → simulation_calls = 0.
                 # engine_type="vlm_glance" → 0 to max_glances (default 3) vision calls per
                 # customer; with the default gating about 1–1.5. shelf_view="photo_chart"
                 # (chart + 3D photo) keeps the count but sends about twice the image per call.

total = generation_calls + simulation_calls
```

Order-of-magnitude reference (assumes a 7-day-open store and ~3 calls per
persona on average):

| Scenario | Personas | Generation | Simulation | **Total LLM calls** |
|---|---:|---:|---:|---:|
| Smoke test | 100 | ~25 | 300 | **~325** |
| Small run | 500 | ~65 | 1,500 | **~1,565** |
| Typical run | 1,000 | ~110 | 3,000 | **~3,110** |

Wall-clock time depends on the provider, model, and concurrency cap. Before
recommending a large LLM run, tell the user the call count and let them
decide. Cheaper ways to get an answer first:

- **`rule_based` engine** — no LLM calls; ~2,400 customers in under 10 s on
  2 CPU cores. Good for layout iteration and as a baseline.
- **Preview runs on a sample** — `max_customers` (UI: *Customers to
  simulate*) simulates a deterministic subset; `preview: true` keeps the
  layout editable.
- **Response cache** — `PARASTORE_LLM_CACHE_DIR` stores every LLM response
  keyed by the full request, so re-running the same configuration costs
  nothing. Combine with `PARASTORE_LLM_SEED` for repeatable sampling.
- **Prefix caching** — the stage-2 prompt puts the store rules and catalog
  (≈95% of its tokens) in a system prefix shared by all customers, so
  providers and servers with prompt caching (Anthropic, OpenAI, vLLM,
  llama.cpp `--cache-reuse`) only process the short per-customer part.

Marketing studio (`/marketing/<project>`):

```
ab_test_calls (rule shoppers)   = 0
ab_test_calls (vision shoppers) ≈ panel × (variants + 1) × 1–1.5    # 0..max_glances per shopper
concept_test_calls              = panel                             # one structured answer per respondent
shelf_test_calls                = 2 × panel                         # control and test shelf per respondent
staff_script_calls              = min(panel, saved_personas) × 2     # separate A and B requests, plus retries
```

shopper_interview_calls         = 1 per question               # text model, from the run's trip log
group_interview_calls           = shoppers + 1                 # one answer each, then theme coding

A concept test with the default 60 respondents is 60 vision calls (cached, so re-running it costs
nothing); an A/B test with three variants on 300 vision shoppers is roughly 1,200–1,800. Run the
rule shoppers first for price and placement questions, and keep vision shoppers for packaging and
signs, which only they can see.

Source: `backend/src/store_emulator/engine/generators/persona.py:99-242`,
`backend/src/store_emulator/engine/simulation/engines/pattern_intent_impulse/engine.py:56-119`,
`backend/src/store_emulator/application/supplemental.py:214-499`.

### Price × sign interaction analysis

For a new **Market → A/B tests** study, create three variants of the same saved layout:

1. **Price-only:** exactly one `price` or `discount` change on a SKU.
2. **Sign-only:** exactly one `promo` change on the same SKU.
3. **Combined:** exactly those same two changes, in either order.

Control supplies the fourth cell. The app's ordinary runner evaluates the same sampled shoppers in each arm.
No extra simulation runs or model calls are added for analysis. Effective layouts must all differ and the
selected arms must have no change-application warnings; no-op factors and additional manipulations are rejected.
Other experiment arms are allowed but are not part of this four-cell analysis. Price/discount factors include
their reference-price/was-price behavior; this is not automatically a pure monetary-price effect.

In the completed report, **Open price × sign analysis**, select the three arms and one whole-basket outcome:
spend in currency minor units, units, or any purchase (0/1). Free purchases count as purchases. Effects are not
SKU-specific sales, daily revenue or realized store results. Rule shoppers treat sign text as a generic impulse
cue; only vision shoppers see it. This does not establish a real POP design's visual effectiveness.

Each new run saves `marketing/experiments/<id>/paired-outcomes.json`, with the request, actual sampled IDs,
effective layout hashes, application warnings and minimal numeric outcomes **before** cohort intersection.
It adds no shopper narrative or new personal data fields. Old aggregate-only runs cannot reconstruct pairs:
the UI explains their unavailability. Invalid identities, contradictory purchase records or outcomes outside
the supported bounds skip optional capture with an English log warning; the existing A/B report can still
complete. Supported values are integer spend 0–1,000,000,000,000, units 0–1,000,000,000 and a Boolean purchase
indicator, for at most 3,000 sampled shoppers / seven arms. Source reads reject files over 8 MB.

With cells 00 (Control), 10 (price), 01 (sign), 11 (both), each complete shopper contributes:

| Contrast | Formula |
| --- | --- |
| Price main effect | `((10−00)+(11−01))/2` |
| Sign main effect | `((01−00)+(11−10))/2` |
| Price × sign interaction | `11−10−01+00` |

The interaction is the difference between the two conditional price effects, not half that difference.
Every cell mean and contrast uses the **same complete four-cell cohort**. Coverage shows both requested and
actually sampled counts and availability in each cell. Missing shoppers/cells are never replaced with zero;
complete-case estimates may be biased. The cohort can differ from the old headline report, which intersects
all experiment arms. With no complete shopper, estimates are unavailable.

Intervals require all actually sampled shoppers in all four selected cells and at least 30 complete shoppers
(an operational guard, not a general statistical guarantee). The engine resamples whole shoppers 4,000 times,
in bounded batches with fixed seed 0. Percentile tails are `0.05/(2×3)` and `1−0.05/(2×3)`: approximately
98.333% per contrast for nominal approximate 95% family coverage of these three contrasts under bootstrap
assumptions. Percentile/Monte Carlo approximations and correlated personas can limit coverage. A point interval
from constant differences does not mean the model or real-world effect is known without uncertainty.

This is **exploratory**, since arms and outcomes are selected after execution. The adjustment does not cover
repeated outcome/arm selection or searches across studies; it does not fix model bias or turn a virtual panel
into a randomized human experiment. No additional p-values or winner are reported. Predeclare analyses and
validate hypotheses independently before drawing confirmatory or real-sales conclusions.

**Export factorial audit CSV** includes method, source SHA-256, simulation and bootstrap seeds, requested
engine/model selection, exact factor changes, counts, formulas, intervals and every sampled shopper's selected
four cells, including incomplete rows with blanks. An empty requested model denotes the app default, not a
pinned model version. The source hash detects source changes; it is not a signature or proof of valid inputs.
Preview/export are read-only. Selections are not persisted; keep the audit. Changing inputs clears the review;
changed/deleted sources reject export. **Reload paired source** retrieves the current hash before a new review.

API: `GET /api/projects/{pid}/experiments/{eid}/factorial/source`, JSON `POST .../preview` and
`POST .../export.csv`; body: `source_sha256`, `price_arm`, `sign_arm`, `combined_arm`, `metric`.

### Inventory performance review

Open **Market → Inventory** in a project. This worksheet uses supplied records without a simulation, model
call or inventory write-back. Choose the inclusive reporting dates (1–3660 days) and an uppercase three-letter
currency code, then **Download inventory template**. The template contains only column names, not sample data.

Prepare one row per exact, case-sensitive SKU, with every numeric cell filled explicitly:

| Column | Meaning |
| --- | --- |
| `sku` | Unique identifier, 1–200 characters; Unicode supported, no outer whitespace or control characters |
| `opening_units`, `closing_units` | Recorded stock at the start and end of the selected period |
| `received_units` | Stock received during the period |
| `sold_units`, `returned_units` | Gross units sold and customer returns, separately |
| `other_in_units`, `other_out_units` | Transfers, supplier returns, write-offs or corrections in the appropriate direction |
| `net_sales_minor`, `cogs_minor` | Net sales excluding tax and net cost of goods sold, after applicable returns/adjustments |
| `opening_cost_minor`, `closing_cost_minor` | Inventory values **at cost**, not selling price |

Use the same period, currency and inventory scope for all rows, and the same unit within each SKU. Quantities
allow 0–1,000,000 and up to three decimal places. Money uses integers in that currency's minor unit (USD cents,
KRW won): net sales and COGS allow ±1,000,000,000,000, inventory values allow 0–1,000,000,000,000. A return-heavy
period can have negative net sales or COGS. Do not invent costs from shelf prices. The currency code is a label;
the app does not verify currency membership, convert amounts or infer the minor-unit scale.

Upload UTF-8 CSV (BOM accepted), at most 2 MB and 2,000 SKU rows. Every template column must occur exactly once;
column order may change. Missing values, duplicate SKUs, extra columns, invalid numbers and oversized files
reject the whole upload. Aggregate repeated rows for a SKU before upload. Include no personal information.

**Review inventory** computes:

- Expected closing = opening + received + customer returns + other in − gross sold − other out.
  Difference = recorded closing − expected closing. A difference is not automatically theft or shrinkage.
- Net unit sell-through = (sold − customer returns) / (opening + received + other in). This explicitly defined
  period convention is shown as a ratio, not a percentage or receipt-cohort rate. Returns are not counted a
  second time in supply. Zero supply or negative net units makes the ratio unavailable; SKU units are not pooled.
- Gross profit = net sales − net COGS. Negative profit remains negative.
- Average inventory cost = (opening cost + closing cost) / 2. This endpoint approximation can miss inventory
  peaks between the two dates. Period GMROI = gross profit / average inventory cost; period turnover = net COGS
  / average inventory cost. Zero average cost is undefined; negative net COGS makes turnover unavailable.

Stock differences, negative expected stock or nonzero value attached to zero stock withhold the affected
SKU's ratios and the portfolio ratios. All supplied records remain in the financial totals. Portfolio ratios
divide totals by summed average costs, never average SKU ratios. Reconciliation alone does not verify the
records or detect every missing transaction or intraperiod shortage. Period ratios are not annualized, net
profit after rent/labor, causal marketing effects or confidence intervals. No universal category targets are used.

**Export inventory audit CSV** includes the exact reviewed period, calculation method, source SHA-256, supplied
values, row results and portfolio totals. Unavailable ratios remain blank with reason flags; spreadsheet formula
prefixes in SKU text are escaped. Keep the original CSV and audit together: reviews are not saved to the project.
Editing the file or scope clears the result and export; controls lock while a request is pending. Separate
reviews do not overwrite one another or update stock. A deleted project prevents subsequent review/export.

API: `GET /api/projects/{pid}/inventory-review/template.csv`; multipart `POST .../preview` and
`POST .../export.csv` with `file`, `start_date`, `end_date` and `currency`.

### Staff script A/B screening

Open **Market → Staff scripts** and select the saved layout. Choose one shelf product, describe the common
encounter (for example, a shopper comparing teas), and supply verified product facts if needed. Enter the exact
current and alternative employee wording, with distinct names. Keep prices, offers and facts the same to isolate
wording. A neutral greeting can be the control. The model is instructed to treat claims in a script as claims,
not verified facts; this is not an automated fact-checking service.

The default is 40 sampled personas and 80 planned text-model requests. At least 20 saved personas are required;
the request is capped at 500. The seed fixes panel selection, first-request order and bootstrap sampling; providers
may still be nondeterministic. Scripts are evaluated in separate requests, without A/B labels, variant names or
the other script. Product, persona and request snapshots are saved under `marketing/pitches/<id>/`.

The report compares **B minus A** on 1–5 purchase intent (primary), trust and pressure. Only personas with both
valid responses enter either mean. Each 95% interval uses 2,000 resamples of paired differences and requires
20 complete pairs. Intervals describe variation in the synthetic panel, not model error or real-customer uncertainty.
A screening leader also requires at least 80% pair completion and no worse mean trust or pressure; those guardrail
means are not a statistical non-inferiority test. Missing intervals mean insufficient pairs, not zero uncertainty.

The paired CSV contains both arms, exact wording, context, product facts, prices, seed, model reference, ratings,
replies, errors and inclusion flags. It retains failures and prefixes formula-like text for spreadsheet safety.
All-model failures are failed jobs; a server restart marks interrupted jobs failed so they can be retried.

Before claiming a sales effect, run a real field pilot: randomize eligible encounters within staff/shift blocks,
record every assigned encounter (including refusals) and purchase, hold the offer constant, and decide the sample
size and stopping rule before reviewing results. This module does not simulate staff availability, spoken tone,
queue time, or store traffic, and does not itself measure real purchases. Use the separate field-pilot workflow below for observed conversions.

### Observed staff-script field pilots

From a completed **Staff scripts** report, open **Prepare a field pilot from these scripts**. Define eligibility
before exposing the assigned script and specify the target-SKU purchase window (for example, this store visit).
Use anonymous staff IDs and distinct shift IDs. Each staff/shift block has an even 4–2,000 planned encounters;
the complete plan has 40–10,000. Choose the fixed target before collecting data; use the optional sample planner below.
The product, price, scripts, context, eligibility, window, seed and allocations are saved and cannot be edited.
No model calls are needed to create or analyze a field pilot from a saved screening report.

Enable **Plan sample size and duration** before saving a new plan. Enter:

- The smallest worthwhile **absolute** conversion difference in percentage points: 5 pp means, for example,
  20% versus 25%, not a 5% relative lift. This is your decision threshold, not a predicted script effect.
- A target power lower bound (50–99%, initially 80%). The planner is deliberately conservative and baseline-free;
  it does not infer conversion from synthetic shopper ratings.
- Estimated unique eligible encounters per operating day across all participating staff/shifts, plus available
  operating days. Use a real operational estimate, not total footfall or duplicate encounters.

The preview compares the current sample with the required total, expected collection days and the **unclipped**
95% interval half-width. Its power figure is a lower bound under the stated assumptions, not estimated actual
power; a zero bound does not mean detection is impossible. The effect can be in either direction. If the required
total fits the existing blocks and the 10,000-encounter limit, **Use recommended counts evenly across these blocks**
updates the unsaved draft. This changes block weights: review the staff/shift mix and each block's capacity.
Requirements beyond capacity are shown in full and are never silently reduced. Days are rounded up, exclude
outcome follow-up, and do not check shift calendars. A sample can fit software limits while exceeding available time.
An under-target plan may still be saved for descriptive learning; it is explicitly flagged as not meeting the target.

For `N` independent encounters, balanced within every staff/shift block and weighted by planned counts, the
existing Hoeffding interval has radius `r = sqrt(2 ln(40) / N)`. If the true weighted absolute conversion difference
is at least `d`, a one-sided Hoeffding tail bounds the probability of failing to exclude zero in that direction.
The power lower bound is `1 - exp(-N × max(0, d-r)² / 2)`. For target power `q`, the required total is
`2 × (sqrt(ln(40)) + sqrt(ln(1/(1-q))))² / d²`, rounded up to an even total, at least 40 and at least four per block.
The 95% two-sided interval already covers either direction; this is one precommitted comparison, not a correction
for multiple pilots. The guarantee is conditional on independent outcomes, no repeat shoppers or interference,
complete enrollment and observation of every planned slot, and no optional stopping or result-driven resizing.
Blocking alone does not remove correlated outcomes within a shift. Do not split an oversized study into repeated
pilots and select the best result. Seek a study-specific design if those assumptions do not fit your operation.

The server recalculates and saves the assessment against the actual counts when **Save fixed pilot plan** is used.
View it later under **Saved sample planning assessment**. It cannot resize a collecting or closed pilot; old pilots
without planning assumptions remain readable. API preview: `POST /api/projects/{pid}/staff-pilots/plan`, JSON
`{"assumptions":{"minimum_effect":0.1,"target_power":0.8,"eligible_per_day":50,"available_days":30},"block_counts":[1000,1000]}`.
These are illustrative inputs, not measured store data. Preview makes no files or model calls. For persistence,
send the same `assumptions` object as the optional `planning` field when creating a new pilot.

Download **Observation sheet CSV**. Within each staff/shift, enroll the next eligible customer before revealing
that row's script; follow sequence order without choosing customers by arm. Do not reuse customers or swap
assignments. Keep the offer and observation process the same in both arms. Edit only these columns:

| Column | 1 | 0 | Blank |
| --- | --- | --- | --- |
| `enrolled` | An eligible encounter received this assignment | This slot was never used | Slot status not recorded yet |
| `delivered` | Assigned script was delivered | Script was not delivered or was refused | Delivery not recorded yet |
| `purchased` | Target SKU bought within the saved window | Target SKU not bought within that window | Purchase outcome unknown |

For unused or unrecorded slots, leave delivery and purchase blank. An enrolled customer remains in their assigned
arm even if delivery is 0 (intention to treat). No customer names, video or receipt details are collected here.

Choose the **full** UTF-8 CSV (up to 2 MB) under **Review full observation sheet**, retaining every row and assignment
column. Selecting a file does not save it. Invalid rows, changed assignments, duplicates and omitted rows reject
the entire preview. Review the before/after table (100 fields per page) and the counts of newly recorded, corrected
and cleared values. A blank **clears** a known observation; it does not preserve the old value. Removal of enrolled
encounters and yes/no purchase reversals are explicitly flagged. Verify corrections against your actual source
records; these checks cannot determine whether a purchase occurred.

Enter an **Import reason** without customer identities or receipt details, confirm that you reviewed the changes,
then choose **Apply reviewed observations**. **Discard preview** leaves the saved records untouched. Applying a
reviewed sheet atomically replaces observations and publishes its import-history reference. The server binds the
review to the exact file bytes, saved observations and revision; a changed file or concurrent update requires a
new preview. Revision checks and file locks reject overlapping updates. A sheet with no changed values adds no
revision or history entry. Downloading **Observation sheet CSV** again returns the current observations.

**Observation import history** retains each committed import's reason, timestamp, revision, CSV SHA-256 and exact
field changes, including previous values. It remains readable after closure and source-screening deletion. Export
all recorded changes through **Export import history CSV**; blank means unknown and 0/1 mean no/yes. Formula-like
reasons are prefixed with an apostrophe in the export for spreadsheet safety. Only committed entries are visible;
an interrupted write may leave an unreferenced detail file that is ignored. Keep `pilot.json` and its `imports/`
directory together when backing up. Missing committed detail files cause an error instead of an incomplete export.
Older pilots disclose where history starts; changes made before this feature were not recorded and cannot be
reconstructed. History records submitted edits, not authenticated reviewer identity or tamper-proof evidence.
Corrections do not relax the fixed sample, no optional stopping, or complete-outcome requirements below.

API clients must first `POST .../staff-pilots/{id}/observations/preview` with multipart `file` and `revision`.
The existing `PUT .../{id}/observations` now also requires the returned `review_token` and a nonblank `reason`
(up to 300 characters), alongside that same file and revision. Read committed details at `GET .../{id}/imports/{revision}`
and the full change export at `GET .../{id}/imports.csv`. The token binds content; it is not authentication or proof
that a person inspected the preview. No raw CSV file is retained and no model call is made.

Opening a saved pilot now starts at **Collection checks**. It shows staff/shift record completeness and a follow-up
checklist without purchase counts or treatment effects. **Observations and results** opens the existing observation
sheet, import review, history and result report. This separation helps monitor collection without reading outcomes;
it is not enforced blinding or a substitute for a fixed stopping rule.

After completing **every planned encounter and purchase/delivery outcome** and closing the fixed plan, open
**Observations and results → Staff and shift sensitivity → Show sensitivity checks**. The report describes how
the B-minus-A target-product conversion difference changes when all blocks belonging to one staff alias, one
shift ID, or one staff/shift pair are omitted in turn. Every group is shown, including those whose removal leaves
no data. Repeated staff aliases across shifts are removed together; repeated shift IDs across staff are removed
together. Use a distinct shift ID for each actual shift and consistent anonymous staff aliases before collection.
Reusing an ID for unrelated shifts or people merges their records; the diagnostic cannot detect or correct that.

Within block `b`, calculate `d_b = purchases_B / planned_B - purchases_A / planned_A`. The full difference is
`sum(n_b × d_b) / sum(n_b)`, with `n_b` the precommitted block size. For each deletion use the same formula over
the remaining whole blocks. These pilots have balanced assignment within each block and require complete outcomes,
so the result also equals the difference between the remaining arms' pooled conversion rates. Refusals and
non-delivery stay in their original assigned arm. No per-protocol subset, missing-value imputation or new model
call is used. The original full-plan result remains primary; deleting groups changes the population represented.

The screen shows the removed sample weight, remaining encounters, deletion estimate, change from the full plan,
range and largest absolute change per scope. Values are absolute percentage points. **Opposite sign** means strictly
positive becomes negative or strictly negative becomes positive; an exact zero is not a reversal. Removing the only
group is **Not estimable**, never zero. Ranges are descriptive, not confidence intervals. Comparisons share data
and are not independent replications. Large changes can reflect noise, composition, heterogeneity or protocol
differences; they do not establish a staff performance effect or diagnose confounding. Stable signs do not prove
causality or fix clustered outcomes, repeated shoppers or interference. Do not choose a favorable deletion, replace
the primary estimate, repeat tests across these rows, or restart pilots for a preferred result.

Open pilots, early closures with unused slots, missing observations and assignments inconsistent with the saved
design are rejected. Do not close early to unlock the report. No stored observations, history, closure state or
primary interval are modified. **Export all sensitivity checks CSV** includes all three scopes and the requested
locked revision. Differences, changes and weights are proportions (multiply differences by 100 for percentage
points); unavailable values are blank. Plan totals repeat per row and must not be summed. Exported formula-like
identifiers are prefixed with an apostrophe. A stale revision must be reloaded instead of mixing snapshots.
API: `GET /api/projects/{pid}/staff-pilots/{id}/sensitivity?revision={revision}` and the same path with
`sensitivity.csv` for export. No extra persisted fields are required for existing saved pilots.

**Observed staff time** connects supplied measurements to the same fixed assignments. Define the timing
protocol before collection and record total active staff seconds alongside the observation sheet's assignment
IDs, including refusals and non-delivery. Use the same start/stop rules in both arms; do not select only buyers.
After closing a fully completed pilot, open **Market → Field pilots → Observations and results → Observed staff time**.
Download a blank template, map your measurements to it, and upload a UTF-8 CSV with exactly these headers
(in any order):

```csv
pilot_id,assignment_id,staff_seconds
pilot_example,assignment_from_the_downloaded_sheet,12.125
```

The example IDs are placeholders; retain the actual generated IDs. No names, timestamps or customer details
are needed. Each assignment may appear once. Times must be blank or decimal seconds from 0 to 3600, with
at most three decimal places. A blank or omitted row is unknown; explicit 0 means verified zero time.
Maximum upload: 2 MB / 10,000 rows. Duplicate IDs, foreign assignments, mixed pilots, invalid numbers and
malformed CSVs are rejected rather than skipped.

Coverage is shown per arm and staff/shift block. Means, maxima and B-minus-A average time are withheld until
**every** planned encounter has a duration, even when one arm alone is complete. Once complete, pooled
averages equal planned-count weighted block averages; delivery and purchase do not change the denominator.
The UI shows up to eight significant digits; the export retains the calculated values. These are descriptive
measurements supplied by the operator, not independently verified timing, confidence intervals, causal
script effects, staffing-capacity estimates or a ranking of employees.

**Export staff time audit CSV** includes every assigned row (unknowns stay blank), source SHA-256, the locked
pilot revision and complete-plan means. The audit is distinct from the three-column upload template.
Review/export does not change or save pilot observations or raw timing files; retain the audit and source
file yourself. Stale revisions and incomplete/open pilots are rejected. Choose any whole-second assumptions
for the cost scenario separately and document rounding; measured fractional means are not silently rounded
or copied into costs. Timing error, future staffing mix and traffic uncertainty remain outside that scenario.

In the same completed, locked pilot, **Staff-script cost scenario** checks whether the conversion difference
could cover extra staff time **under your explicit assumptions**. Enter all five values; none is inferred from
the product price, synthetic ratings or POS records:

- **Contribution per converted encounter:** a common net contribution from the target product for a buyer in
  either arm, after product costs, discounts and returns, before staff time entered here. Use currency minor
  units (USD cents, KRW won). It is not selling price, basket revenue or per-unit margin unless one unit per
  buyer is justified. A different contribution per buyer in A and B is outside this model.
- **Loaded labor cost per hour:** the assumed cost of staff time in the same currency's minor units. Avoid
  counting the same labor cost both here and in contribution.
- **Average staff seconds per assigned encounter, A and B:** whole-second assumptions across all eligible
  assigned encounters, including refusal and non-delivery, not just buyers or delivered scripts.
- **Assumed eligible encounters per day:** the daily scenario volume for the same eligible population and
  staff/shift mix. This is not measured footfall or a staff-capacity calculation.

Blank means unknown; enter zero explicitly if justified. Money inputs are bounded at 1,000,000,000 minor units,
time at 3,600 seconds per encounter and daily volume at 1,000,000. Let `m` be contribution per buyer, `h` hourly
labor cost, `tA/tB` the average seconds and `d` the full-plan B-minus-A conversion difference. Incremental labor
per encounter is `c = (tB - tA) × h / 3600`; incremental contribution is `d × m - c`. The break-even difference
is `c / m`, shown in percentage points without clipping. A threshold outside −100 to +100 pp is disclosed.
At zero contribution the threshold is undefined and only the assumed labor difference remains. A cheaper B
can have a negative threshold. Expectations can be fractional minor units; they are not rounded to whole cents
or won in the CSV. The screen also uses minor units and preserves small nonzero values.

**Calculate cost scenario** transforms the original conservative fixed-sample 95% conversion interval by the
same `× m - c` formula. This is a range for mean incremental contribution **conditional on fixed costs**; it
does not include uncertainty in contribution, labor, time or traffic. Daily values multiply each bound and
estimate by the entered eligible volume. They are not prediction intervals for realized daily profit. Product
mix, other basket effects, fixed implementation costs, capacity changes and future demand are excluded. Reusing
the pilot with different cost inputs creates scenarios, not new evidence or independent tests; do not select
favorable assumptions to claim a confirmed profit effect. The original stopping rule and full-plan result remain.

The same complete fixed assignments and known purchase/delivery records are required; no unused or missing rows
are dropped, and non-delivery stays in its assigned arm. The calculation does not repair clustering, repeated
shoppers, confounding or a changed offer. No observation, design, history or closure state is modified. Scenarios
are not persisted: **Export cost scenario CSV** retains the exact successful input snapshot, source revision,
currency, formulas' inputs and outputs. Conversion differences use proportions in CSV (multiply by 100 for pp);
an undefined threshold is blank. Editing any input clears the old result/export. Both preview and export reject
stale revisions. API: `POST /api/projects/{pid}/staff-pilots/{id}/economics` and `economics.csv`, JSON with
`revision`, `currency`, `contribution_per_conversion_minor`, `labor_per_hour_minor`, `seconds_per_encounter_a`,
`seconds_per_encounter_b` and `eligible_encounters_per_day`. No live model call is made.

For observed POS evidence, open **Observations and results → Reconcile POS purchases**. Prepare a UTF-8 CSV with
the following columns (each exactly once, any column order):

```csv
pilot_id,assignment_id,transaction_id,sku,net_quantity
```

Use the saved pilot ID on every row and the immutable assignment IDs from its observation sheet. Link encounters
to anonymous transaction tokens using your local source records; TwinStore does not infer these links from names,
times or receipt totals. Tokens must start with an ASCII letter/digit and contain only letters, digits, underscore,
hyphen, period or colon, at most 120 characters. Use tokens unique across stores and dates. Leave `assignment_id`
blank to expose unlinked transactions, and omit personal/payment data. Unknown nonempty assignment IDs are listed
for review; a different pilot ID rejects the upload.

Each row is one **transaction/SKU aggregate**, net of returns, for finalized sales inside the saved outcome window.
Combine duplicate item lines before upload. `net_quantity` accepts nonnegative decimals up to 1,000,000 with at most
six decimal places; negative returns, exponents and nonfinite numbers are rejected. Resolve returns against their
original transaction before preparing the extract. SKU matching is exact and case-sensitive, preserving leading
zeroes. Input is limited to 2 MB and 10,000 item rows. Duplicate transaction/SKU rows and a transaction linked to
multiple assignments (including a linked/unlinked mixture) reject the entire preview.

| Match status | Candidate observation change |
| --- | --- |
| Positive target units, enrolled, purchase unknown | Proposes `purchased=1` |
| Positive target units, purchase already yes | Keeps the known value |
| Positive target units, purchase recorded no | Flags a conflict; keeps no until separately verified |
| Positive target units, enrollment unknown or unused | Flags enrollment; never enrolls an encounter automatically |
| No matching target SKU or zero net units | Keeps the saved purchase value, including unknown |
| Unknown assignment or blank link | Lists the source tokens; does not change any assignment |

Several receipts for one encounter produce at most one proposed conversion. Enrollment, delivery (including
refusals), staff, shift, arm and all other outcomes remain unchanged. The “without positive evidence” count measures
coverage of this file among enrolled encounters; it includes recorded buyers absent from the extract and is neither
a missing-outcome count nor a nonbuyer count. Partial POS coverage must never be treated as evidence of nonpurchase.

Filter and page through the matches, verify assignment links, finalized net sales and the outcome window, then choose
**Review proposed purchase changes**. Screen filters do not change the candidate. This opens the existing full-sheet
diff; inspect it and enter/confirm a reason before applying. The default editable reason includes the source CSV
SHA-256. Both preview and apply check the visible pilot revision, and closed pilots reject reconciliation. Discarding
either preview saves nothing. After application, existing history records the purchase changes and reason, and the
collection checklist refreshes. No direct save bypasses the normal review token, concurrency lock or closure rules.

No raw POS file, transaction registry or match report is retained. Duplicate checks are **within this CSV only**;
reused transactions across separate uploads or pilots cannot be detected. Maintain a complete reconciled local
extract and check reuse in your source system. Source hashes identify bytes, not verified sales or authenticated
reviewers. Time windows, finalized status, returns and customer identity are operator-verified assumptions. The
module does not correct repeated shoppers, uneven capture, staff/shift confounding or optional stopping, and does
not estimate revenue or script effects. Use the same outcome-capture procedure for both arms.

API: `POST .../staff-pilots/{id}/pos/preview` with multipart `file` and `revision` returns matches, source metadata
and `candidate_csv` without writing. To apply a candidate, use the normal `observations/preview` and `observations`
endpoints with the returned revision; never silently substitute a newer revision after a conflict. Existing pilots
need no migration. This assignment-level input is separate from the aggregate POS simulation-validation upload.

The checklist distinguishes four cases:

| Check | Meaning | Follow-up |
| --- | --- | --- |
| Purchase outcome unknown | An enrolled encounter has no recorded purchase outcome | Verify after the saved outcome window; do not turn an unknown into a nonbuyer |
| Script delivery unknown | An enrolled encounter has no recorded delivery status | Verify delivery; a refusal remains enrolled with delivery recorded as no |
| Enrollment record gap | A blank enrollment status precedes a later recorded status in the same staff/shift | Check the original records; the gap does not prove an assignment was skipped |
| Unused slot before later enrollment | A slot marked unused precedes an enrolled encounter in the same staff/shift | Review sequence use; correct only a verified recording error |

**Unrecorded tail slots** follow the last recorded enrollment status in each staff/shift. They may be future slots
or unentered records; they are not known missing customers and do not create follow-up tasks automatically. An empty
checklist therefore does not mean the sample is complete. The separate readiness message retains the existing rules:
every slot must be recorded and all enrolled purchase/delivery outcomes known before closure; any unused slot leaves
the study below its full planned target. Sequence-review flags remain visible after closure but do not independently
block it or certify protocol compliance.

Expand a staff/shift to inspect A/B denominators. Purchase missingness is unknown purchases divided by enrolled
encounters. Non-delivery is recorded non-delivery divided by enrolled encounters with known delivery status; it
includes refusals and does not remove customers from their assigned arm. Zero denominators display **Unknown**.
The B-minus-A missingness gap describes record completeness only, without a hypothesis test or a claim of staff
performance, treatment effect, or confounding correction. No timestamps are available to classify tasks as overdue.

Filter the screen by staff/shift and check type; the checklist paginates at 50 assignments. **Download all follow-up
checks CSV** always exports all checks at the latest saved revision, with one row per issue (an assignment can have
two), revision/time metadata and suggested actions. An empty checklist exports column headers only. It is a checklist,
not an importable observation sheet. Resolve
verified corrections through the existing full-sheet review so revision checks, reasons and history remain intact.
Reload collection checks after external changes; in-app imports and closure invalidate the cached checklist.
The read-only endpoints are `GET .../staff-pilots/{id}/collection-checks` and `GET .../{id}/follow-up.csv`.
They work for older pilots and closed pilots without adding new saved fields or making model calls.

Under **Observations and results**, the dashboard shows recorded rates and worst/best missing-outcome bounds over enrolled
encounters. These bounds are **not confidence intervals**. Unknown purchases do not become nonbuyers. Staff/shift
rows expose uneven enrollment; non-delivery counts remain visible. No treatment-effect interval is shown while open.

Once every slot is marked enrolled or unused and every enrolled outcome and delivery status is known, **Close and
lock pilot** ends collection. This cannot be reopened or overwritten. If any planned slot was unused, the closed
report stays descriptive. When the entire target is completed, B minus A is weighted by precommitted staff/shift
sample sizes. Its conservative 95% Hoeffding interval remains nonzero at all-zero or all-one outcomes. It assumes
independent encounters, no repeat shoppers or interference, and a fixed stopping rule; it does not account for
unmodeled clustering, repeated peeking, or selecting the best of multiple experiments. It is intentionally wider
than common asymptotic intervals. A positive interval is evidence for the measured conversion outcome under those
assumptions, not a store-wide sales or profit forecast.

All saved pilots are accessible under **Market → Field pilots**, even if their source synthetic test is later
removed. Plans and observations are stored in `marketing/field-pilots/<id>/pilot.json`. They contain observed records
only; no synthetic responses are mixed into the conversion counts. The implementation is verified with offline
fixtures; operators must supply real records to evaluate a real store.

## Step 1 — Store info

| Field | Type | Fed to LLM? | What "good" looks like | Silent failure mode |
|---|---|---|---|---|
| `name` | text | no — metadata only | Any non-blank label | — |
| `description` | text | no — metadata only | Any | — |
| `address` | **free text** | **yes** — location analysis, daily traffic, persona batch | "123 Teheran-ro, Gangnam-gu, Seoul — office district, two blocks from subway" | "Store 1", "Korea", any string without a neighborhood / use-context anchor → LLM falls back to generic demographics |
| `store_type` | **free text** | **yes** — persona + pattern + impulse prompts | "Convenience store", "Independent bookstore", "Specialty coffee shop" | "Shop", "Place" → pattern selection LLM cannot anchor product categories |
| `working_day_preset` | enum: `7` / `weekday` / `weekend` | no, but drives `N_open_days` | Match the user's real schedule | — |
| `open_hour`, `close_hour` | int, 0–24 | yes — traffic LLM uses the window | Realistic per `store_type` (e.g. `[7, 23)` for convenience) | `[0, 24)` default rarely matches reality and inflates the visitor pool |

`address` and `store_type` are the two most common silent-failure inputs.
Push the user to be specific before submitting the form.

## Step 2 — Customer profile and supplemental file

### `customer_profile` (required free-text textarea)

This single field is referenced in **five** prompts: location analysis,
daily traffic, persona generation, pattern selection, and impulse
purchases. It's the highest-leverage input the user touches.

Validation only checks that it's non-blank — anything past that is on the
assistant to coach.

A well-formed profile names three things:

1. **Segments** — who shops here.
2. **Timing** — when each segment shows up.
3. **Behavior** — what they tend to do.

Example (matches the in-app placeholder):
*"Office workers during lunch (12:00–13:30) grabbing prepared food and
drinks to go; local residents in the evening doing small top-up shops,
often with a child in tow."*

Things to push back on:
- One-line profiles like "busy store" or "various customers."
- Segments that contradict the operating hours (e.g. "late-night
  customers" with a 07:00–22:00 schedule).
- A single segment when the store type usually serves several.

### Supplemental file (optional, ≤10 MB, `.csv` or `.xlsx`)

**There is no fixed schema.** This surprises many assistants. The
pipeline is content-agnostic
(`backend/src/store_emulator/application/supplemental.py:161-499`):

1. Load the file, cast every column to string.
2. An LLM picks which columns look meaningful from the column metadata
   and a 5-row sample.
3. Per-column statistics get computed (numeric `describe()`, datetime
   min/max, top-10 categorical frequencies, optional hourly groupby if a
   datetime column is present alongside numerics).
4. An LLM writes a ≤2000-character prose summary, which is appended to
   the persona-generation prompt.

What lands well:
- POS sales logs.
- Hourly or daily visitor counts.
- Demographic surveys keyed to time-of-day.

What lands poorly:
- Sheets that are all-NaN or single-value columns (Stage 3 filters them
  out, leaving an empty summary).
- One free-text column with no structure (the summarizer has nothing to
  aggregate).

**All failure modes are silent.** Malformed files don't raise errors —
they just produce an empty `supplemental_summary`, and generation
proceeds without the data-driven refinement. After upload, point the user
at the generated summary (stored in project metadata) so they can
sanity-check that something useful came through.

## Pre-flight checklist

Run through this before triggering generation or simulation:

- [ ] `address` includes a neighborhood or use-context, not just a name.
- [ ] `store_type` is specific enough to anchor product categories.
- [ ] `customer_profile` covers segments + timing + behavior.
- [ ] `customer_profile` does not contradict operating hours.
- [ ] Operating hours are realistic for the store type (not `[0, 24)`
      unless the store actually runs 24/7).
- [ ] If a supplemental file is uploaded, the relevant sheets are
      non-empty and contain at least one numeric or datetime column.
- [ ] The user has been told the expected LLM call count for the chosen
      persona size (or chose the `rule_based` engine / a customer sample).
- [ ] For a layout comparison, both runs use the **same seed** and the same
      engine, so the comparison is paired (the Compare dialog warns otherwise).
- [ ] `PARASTORE_CURRENCY` matches the price unit of the catalog (prices in
      KRW are whole won; in USD they are cents).

## Constraints worth knowing

- **Behavior patterns are a fixed preset of 10**
  (`backend/src/store_emulator/application/presets/behavior.py`):
  `purposeful`, `habitual`, `routine_refill`, `urgent`, `quick_snack`,
  `exploratory`, `hungry_wandering`, `leisurely`, `social_browsing`,
  `impulse_heavy`. The wizard does not let users add or edit them; doing
  so requires a code change.
- **Starting layout is optional.** With **Start with a furnished store
  template** checked, the wizard creates the project with one of the 54
  generated layouts (no LLM call). Unchecked, the project has no store
  layout, and simulation cannot run until the user builds a grid in the
  layout editor (`/features/grid-editor/`) or imports a floor plan.
- **Hidden inputs not exposed in the wizard**: `custom_instruction` and
  `max_persona_count_per_day` are accepted by the regenerate API
  (`backend/src/store_emulator/application/generation_async.py`) but
  have no UI yet. If the user asks how to constrain persona generation
  further, these are the levers.
- **Choosing the LLM provider.** Default model is
  `anthropic/claude-haiku-5-5` (`LLMConfig.model` in
  `backend/src/store_emulator/application/config.py`): an Anthropic key
  (Settings → Model providers, or `ANTHROPIC_API_KEY`) is all it needs.
  Without one, the set-up helpers, interviews and persona generation use a
  fast model of another provider that has a key, and with no cloud key at
  all the local model TwinStore runs for vision shoppers once it is ready
  (slower, and weaker on long structured answers). To make another model
  the default, set `PARASTORE_LLM_MODEL` to its LiteLLM model string *and*
  the matching `*_API_KEY` in `backend/.env`. For a self-hosted
  OpenAI-compatible server also set `PARASTORE_LLM_API_BASE`
  (e.g. `PARASTORE_LLM_MODEL=openai/local`,
  `PARASTORE_LLM_API_BASE=http://127.0.0.1:8080/v1`). Small local models
  (≤4B) tend to fail the structured stage-2 output on large catalogs; use
  `rule_based` for local-only setups.
- **Customers per day.** The model writes every visitor a day's traffic
  estimate expects, up to 1,000 (`PERSONA_DAILY_POPULATION`);
  `PERSONA_DAILY_CAP` (default 1,000, at least 10) lowers how many it
  writes, with twins of the written customers filling the rest of the day.
  When writing them all would take about 10 minutes or cost about $1, the
  app asks first (all of them, a quick sample of 100 a day — 20 on the
  local model — or cancel); `POST …/generations/{gen_id}/confirm` answers
  it over the API.
- **Stage 3 is conditional.** Impulse purchases only run when a persona's
  walked route exposes at least one stocked product. With the default
  `visibility` exposure model a product counts as seen only if its rack
  face is in view (distance, 45° cone, line of sight, shelf level); the
  legacy rule (any adjacent tile) is `PARASTORE_EXPOSURE_MODEL=adjacency`.
- **Runs are reproducible.** Cues, arrival minutes, glances and engine seeds
  derive from `(seed, replicate, persona id)`. Two layouts run with the same
  seed see the same customers in the same states, which is what makes the
  A/B comparison paired. Use different `replicate` values for independent
  repetitions of one layout.
- **Not every visitor buys.** Patterns that allow it may leave empty-handed,
  and impulse purchases beyond `budget_max × PARASTORE_BUDGET_TOLERANCE`
  (default 1.5) are dropped. Check *Run diagnostics* for dropped
  hallucinated or over-budget items and failed customers.
- **Validating against real sales.** *Validate against POS data* (or
  `parastore fidelity RUN pos.csv`) accepts CSV/XLSX exports with columns
  like `receipt_id`, `sku`/`product_name`, `qty`, `unit_price`/`sales_value`
  and `timestamp`/`hour`; SKUs are matched to catalog ids or names. Only
  products present in both are compared, so check the reported coverage.
- **Receipt-photo review.** In a run's sales-validation section, **Receipts**
  reads photos into an editable draft. Confirm each product against the saved
  run's catalog, correct quantity and prices in minor currency units, and
  exclude duplicate photos, returns or unreadable receipts. **Check receipts**
  flags unknown products, missing amounts, duplicate IDs and currency mismatch.
  A printed line total takes precedence over unit price × quantity so discounts
  and total-only lines retain their paid value. Review subtotal warnings for
  tax or excluded lines; those exclusions change basket comparisons. Set a local
  date and time, or clear the timestamp to omit hourly scoring. Only **Use reviewed
  receipts** sends the checked batch to POS validation; editing invalidates the
  previous check. OCR and manual review are not proof of real-world forecast accuracy.
- **Validating observed movement.** In a completed run, **Validate real movement**
  accepts UTF-8 CSV with `track_id,x,y,timestamp_sec` (up to 10 MB / 100,000 samples).
  Extract anonymous tracks on your device and align them to this run's grid first:
  integer cells, origin at the upper left, x right and y down. Each visit needs a
  distinct ID across the file; seconds must increase within a track. Rows may be
  interleaved or unsorted. Duplicate identical samples are collapsed; conflicting
  positions at the same timestamp are rejected. This module imports coordinates;
  it does not upload video, detect people or perform camera calibration.
  Visitor maps count each track once per cell. Occupancy assigns an interval to
  its starting cell and excludes gaps over the chosen threshold (default 30 s);
  the last sample adds no time. Compare equivalent layouts and operating periods
  with adequate camera coverage. The report shows normalized map similarity and
  visitor-share gaps, persists only aggregate data in `output/movement.json`, and
  leaves simulator parameters unchanged. Use the gaps to select regions for a
  calibration experiment; partial camera coverage is not evidence of low demand.
- **Restocking priorities.** Shelf Lab's completed compliance audit includes a
  planner for missing SKUs. Set the recovery horizon in trading days, blended
  contribution margin and extra handling/delivery overhead per SKU (minor units).
  The initial 1 day / 30% / zero overhead values are editable planning assumptions.
  Net contribution is `isolated daily revenue effect × days × margin − overhead`;
  confidence limits use the same transformation. Items with positive lower bounds
  appear first, and unestimated items remain visible. Missing levels of one SKU
  share one action. **Locate** highlights the photo region; **Export restocking CSV**
  includes source audit IDs, assumptions and uncertainty for a task sheet.
  The estimates assume constant demand and exclude operational uncertainty.
  Do not add SKU effects: the audit evaluates each stockout against the otherwise
  stocked reference, so joint recovery can differ because of substitution.
- **Restocking quantities and budget.** In the same completed audit, enter verified
  additional shelf units needed, available stockroom units, units per supplier pack,
  pack cost in the audit currency's minor units, supplier available packs and priority
  for each included SKU. Quantities start blank: an unknown is not zero. Required units
  cover all listed levels of that SKU together; facings and modeled losses are never
  converted into inventory counts. For counterfactual photos, check the actual store
  before entering quantities. You can include 1–200 identified missing SKUs; excluded
  SKUs and unidentified missing findings are disclosed in the result and CSV.
  The total purchase budget and one delivery fee also use whole minor units (USD cents,
  KRW won). Include taxes and applicable charges in the supplied prices; no FX conversion
  is performed. Quantities/pack availability are capped at 1,000,000 and monetary inputs
  at 1,000,000,000,000 minor units.
  **Calculate restocking quantities** uses stockroom units first, then rounds the
  remaining need up to whole packs. It allocates packs by ascending operator priority
  (1 first; ties use case-sensitive SKU order), respecting supplier and budget limits.
  The initial priority follows audit order, not modeled benefit. Partial fulfillment
  leaves unfilled units; pack rounding can create surplus units. A cheaper later item
  may fit even when an earlier pack is unaffordable. This is a sequential allocation,
  not an optimal-profit solution. It never adds the isolated revenue effects.
  The delivery fee is reserved once and charged only if at least one pack is ordered,
  including zero-cost packs. A stockroom-only plan incurs no delivery charge. Use a
  separate plan for separate suppliers or fee structures. Results show line costs,
  supplier/budget constraints, total spend and unspent budget. Editing any input clears
  the prior result and export until recalculated. **Export quantity plan CSV** includes
  the source audit, inputs, excluded SKUs and quantities; plan-level budget/cost fields
  repeat on each row and must not be summed. `goods_cost_minor` is the line cost.
  Plans are not saved in the project; keep the exported worksheet. This feature places
  no order, reserves no stock, changes no layout and makes no model call. Verify storage
  capacity, expiry, lead time and supplier prices separately. Reusing the same stockroom
  units in another plan can double-allocate them. No real-sales effect is inferred.
  API: `POST /api/projects/{pid}/captures/{cid}/lab/jobs/{jid}/restock-order` accepts
  `currency`, `budget_minor`, `delivery_fee_minor` and `items` (`sku`, `required_units`,
  `stockroom_units`, `pack_size`, `pack_cost_minor`, `max_packs`, `priority`). The `.csv`
  suffix exports the same plan from the same JSON body. Both require a completed saved
  audit, matching currency and identified missing SKUs; duplicate SKU rows are rejected.
- **Selecting a PDF floor plan.** **Add layout → From a floor plan** previews
  PNG/JPEG/WebP images and multi-page PDFs. Choose the page and clockwise rotation,
  confirm the preview, then create the layout. Preview does not call a vision
  model or create a layout. PDF support is installed by default. Uploads are capped
  at 25 MB; images at 25 megapixels; rendered pages at 2,400 pixels on their longest
  side. Import notes record the source page and rotation. The grid is still an
  approximate reconstruction: review fixture positions, aisles and entrances.
- **All run artifacts live in `backend/.data/`**, which is gitignored.
  Persona files, simulation results, and generated metadata never leave
  the local machine unless the user copies them out.

## When to escalate to the user

Stop and ask before:

- Triggering a generation run larger than ~1,000 personas — confirm
  the user understands the LLM cost.
- Auto-filling `customer_profile` or `address` from thin context. These
  are the inputs the simulation hinges on; a guess here propagates
  through every downstream prompt.
- Mutating files under `backend/.data/` — those are the user's runs and
  may be irrecoverable.

### Observed competitor unit prices

Open **Market → Unit prices**, download the blank offer template, and supply operator-verified observations.
Set the exact focal retailer ID, as-of date and maximum observation age (0–365 days, inclusive; zero means
that date only). This read-only worksheet is independent of the selected simulation layout and makes no model calls.

| Column | Meaning |
|---|---|
| `offer_id`, `retailer` | Exact, case-sensitive IDs; one observation per retailer/offer pair. Choose the observation before upload; duplicates are rejected, not silently replaced with the latest. |
| `comparison_group` | Operator-asserted comparable product/quality group; use consistent tax, deposit, delivery and channel treatment. No automatic SKU matching. |
| `observed_on`, `currency` | ISO date `YYYY-MM-DD` and three uppercase currency letters. Currencies remain separate; no conversion. |
| `pack_count`, `quantity_per_pack`, `unit` | Total bundle quantity is count × quantity; units `g`, `kg`, `ml`, `l`, `item`. Mass normalizes to kg, volume to l; count stays separate. |
| `price_minor` | Total payable bundle price, in integer minor units (USD cents, KRW won). Explicit zero is allowed. Do not use a per-pack price for a multipack. |
| `availability` | Exactly `in_stock`, `out_of_stock` or `unknown`. Only `in_stock` qualifies. |
| `terms` | `public` or `conditional`; member/coupon/eligibility offers are conditional and excluded. No inferred promotion arithmetic. |

UTF-8 (optional BOM), exact template headers in any order, at most 2 MB / 2,000 rows. IDs have 1–120 characters
without outer whitespace or control characters. Pack count is 1–1,000; quantity per pack is positive, at most
1,000,000, with up to three decimals (whole counts for `item`); price is 0–1,000,000,000,000 minor units. Missing values are not zero.

Each product group/currency/base-unit comparison uses the lowest qualifying focal offer and lowest qualifying
competitor offer, with all exact ties and eligible offer/retailer counts. It is an observed minimum, not an average,
market census, optimal price or sales effect. Gap = focal − competitor; percentage gap divides by competitor price
and is unavailable for a zero competitor price. Missing sides remain unavailable. Comparisons use exact rational
arithmetic before rounding display values to 12 significant digits. Displayed minima can round alike while their
exact relation still differs. Source rows and exact rate/gap fractions are retained in the audit CSV.

Future, stale, conditional, out-of-stock and unknown-stock observations are retained with reasons but excluded.
No offer being present does not prove an assortment gap. The operator must verify comparable quality and pricing
scope. The tool does not implement a jurisdiction's price-label compliance rules, modify prices, or feed observed
price differences into a demand model. No significance tests, repeated-test claims or staff/shift aggregations occur.

Download the audit and keep the original file: reviews are not saved. Editing scope clears the displayed result;
inputs lock during requests; export resubmits the reviewed file and scope with its source SHA-256. Changed bytes
return 409; a deleted project returns 404. Concurrent read-only reviews do not overwrite one another.
API: `GET /api/projects/{pid}/unit-prices/template.csv`, `POST .../preview`, `POST .../export.csv` (multipart CSV,
`focal_retailer`, `as_of`, `max_age_days`; export additionally requires `source_sha256`).

### Research protocols and amendments

Open **Market → Protocols** to record an original plan or open a saved history. This module is independent
of the selected layout and uses no model calls. It records plans; it does not enforce them on simulations,
change field-pilot assignments, calculate power or certify study validity.

Record a title, synthetic/observed evidence source, research question, population/sampling, design/assignment,
primary outcome with units and window, independent analysis unit, planned independent-unit count (1–1,000,000),
exclusions/missing-data rule, stopping/interim rule and analysis/multiplicity plan. State staff/shift clustering
and repeated observations where relevant. Title limit: 120 characters; each plan text field: 1,500 characters.
No personal details or secrets. Text is trimmed; Unicode and line breaks/tabs are accepted, other controls rejected.

Explicitly declare **Data not collected**, **Data collected; results unseen**, or **Results already seen**.
This is your declaration, not an independent check. A first record can already be retrospective. Later records
cannot move the declared stage backward; a different study should get its own protocol.

Every amendment needs the current saved head and a reason (1–1,000 characters). The original plan and full
snapshots remain in history. The UI shows field differences from each preceding revision and differences from
the original plan. Planned-unit delta is withheld if the analysis-unit text or evidence source changed;
matching text alone cannot verify actual comparability. Declaring a later data stage without changing the plan is a meaningful amendment; an unchanged
plan/stage with only a new reason is rejected. Maximum 50 revisions per protocol and 100 protocols per project.

Inputs lock during requests. Export is disabled for unsaved edits; **Reload saved version (discard draft)**
explicitly replaces the draft with saved data. A save may complete after navigating away: reload the protocol
list to check. Create requests use an idempotency ID, so retrying the same submitted creation cannot duplicate
the record. Reusing that ID for a different original plan returns 409. Concurrent amendments and stale heads
return 409; reload and review differences rather than overwriting another editor's change.

**Export saved history JSON** includes complete snapshots, derived differences, method notes and the hash chain.
**Export saved changes CSV** gives one row per changed field, including original fields, revision timestamp,
reason, data-stage declaration and hashes; text is spreadsheet-escaped. Downloads require the displayed head,
so changes in another session cause 409 instead of an unnoticed export of a different revision.

History is stored under `.data/<project>/marketing/protocols/<protocol_id>.json` with a project-level file lock
and atomic replacement. Reads are bounded to 4 MB and validate schema, project/record identity, sequence,
parent hashes, content hashes and forward-only data stages. A corrupt record is listed as unavailable while
other histories remain accessible; preserve the file and restore a verified backup. The app does not offer
revision edit/delete or import endpoints.

This is **not external preregistration or a trusted timestamp**. The server clock and declared stage cannot
prove data were unseen. Someone with file access can replace the whole history and recompute hashes; local
hash checks establish internal consistency, not authenticity, authorship, permanence or independent registration.
Keep exported originals separately if needed and use an appropriate external registry for registration.
Synthetic plans/results do not establish actual sales effects; no outcomes or statistical tests are performed here.

API: `GET/POST /api/projects/{pid}/protocols`; `GET .../{protocol_id}`;
`POST .../{protocol_id}/amendments`; `GET .../{protocol_id}/export.json?head=<sha256>` and
`GET .../{protocol_id}/changes.csv?head=<sha256>`. Creation: `request_id` (32 lowercase hex), `plan`, `data_stage`.
Amendment: `expected_head`, full `plan`, `data_stage`, `reason`. JSON schema rejects unknown keys.

### Observed shelf and checkout price checks

Open **Market → Price checks**. Download the blank template, fill one file from verified shelf-label
observations and a separate file from checkout checks, then enter a store reference and audit date.
No simulation or model is called. Uploaded observations remain local request inputs; reviews are not saved.

Both files use `check_id,sku,pack_reference,checked_on,currency,price_minor,terms`:

- Assign one exact, case-sensitive `check_id` to each intended label/checkout pair. A missing side remains
  visible; a header-only source is permitted, but at least one observation overall is required. Duplicate
  check IDs within either file are rejected. Multiple checks of one SKU are allowed, not independent samples.
- `sku` and `pack_reference` must agree on both sides. The latter identifies the full item/package quantity.
  Verify item equivalence, price timing, channel, tax and deposit treatment yourself; matching IDs do not prove it.
- `checked_on` and the audit date use `YYYY-MM-DD`. Both observations must fall on that date. Different-date
  observations stay in the audit but do not produce a difference. No time-of-day matching is inferred.
- `currency`: three uppercase letters; no currency conversion. `price_minor`: integer full payable item/package
  price in currency minor units (USD cents, KRW won), 0–1,000,000,000,000. Explicit zero means free, not missing.
  Do not supply baskets or prices requiring weighted-goods, multibuy, membership or coupon calculations.
- `terms`: `public`, `conditional` or `unknown`. Only public/public pairs qualify. Unknown is not assumed public.
- UTF-8 CSV (BOM allowed), 0–2,000 rows and at most 2 MB per file. No unknown/missing/duplicate columns.
  Identifiers have 1–120 characters, no outer whitespace or control characters. Do not include personal data.

The table retains the full union of IDs, both sources and all exclusion reasons. For comparable pairs,
`difference_minor = checkout − label`. Totals are separated by currency and report higher/lower/equal counts,
positive sum, negative sum and net sum. A zero net can conceal opposing discrepancies. These are sums of one
price difference per check, **not** purchased quantities, customer losses, refunds, revenue effects, employee
performance or a representative store error rate. There is no significance testing or repeated-look inference.

Export the audit CSV and retain both originals. Export resubmits exactly the reviewed files and scope and
requires the combined SHA-256 digest; mismatches return 409. Changes to either input clear the old result.
The digest identifies bytes and scope, not authenticity. The audit CSV escapes spreadsheet formula-leading
text; numeric signed differences stay numeric. Missing observations/differences are blank, not zero.

This is a discrepancy worksheet, not a legal compliance verdict. Source-based requirements, limits and actual
checks are recorded in `verification/2026-10-21-price-check-candidates.md` and
`verification/2026-10-21-price-check-review.md`. Actual store data and operator usability were not tested.

## Combine reviewed shelf photos into one layout

Open the project's **Capture** screen. Upload/recognize each photo with the existing uploader, then
use **Review** to correct its names, prices, shelf levels and facing counts. When at least one capture
exists, **Combine reviewed shelf photos** appears below the photo strip:

1. Choose a **Base layout**. Select completed, nonempty photos individually or use **Select first 20 ready photos**.
2. Select **Preview combined layout**. Inspect the floor plan, new rack IDs, product/facing counts, and
   estimated or missing prices. The placement follows selection order. No new model call is made here.
3. If whole products do not fit, correct the photo or choose more free floor space and preview again.
   If facing counts shrink to fit the grid, explicitly accept the displayed reduction before saving.
4. **Save combined draft** writes one new child layout and registers available product crops. Existing
   products, source layouts and captures stay intact. **Open combined layout** opens the result for editing.

Complete normalized product names (including brand and size) can reuse an existing SKU; similar names
are kept separate. This is name matching, not barcode verification. Review the result before simulation.
Unrecognized products and missing/estimated prices remain review warnings. Missing prices may appear as
zero in the grid: this is a placeholder, not an observed zero price. Correct these in the photo before saving.

Up to 20 captures, 2,000 total facings and 24 facings per product are accepted. Every photo must match the
base layout's currency; prices are never converted. Photos add racks onto free floor next to aisles, using
existing shelf-level and left-to-right grid mapping. They do not recover camera geometry, exact dimensions,
room locations or stock quantities; grid capacity may reduce facings. Use the photo intake queue below to
upload several images; each still uses the existing single-photo recognition pipeline.

If a photo or base store changes after preview, save is rejected: preview again. After an uncertain save
failure, **Retry saving this draft** reuses the same request and returns the existing draft if it was already
written. Keep the current combined preview open for this retry; combined previews are not persisted across
reloads. After reload, inspect Layouts for the saved combined draft before making another one. Crop image
writes use the existing shared SKU image storage; a failed layout write can leave newly registered crops,
and existing images are retained. No source layout or capture is deleted by this action.

API: `POST /api/projects/{pid}/captures/batch-preview` accepts `capture_ids` and `setup_id`.
`POST .../captures/batch-save` additionally requires the returned `source_sha256`, a stable 32-character
lowercase hexadecimal `request_id`, and `allow_reduced_facings: true` when the preview reports a reduction.
The same request ID must be reused unchanged after an uncertain save; a different payload returns 409.

## Upload several shelf photos with a controlled queue

In **Capture**, choose **Add photos** (or use the upload panel in an empty project). Select recognition
settings first, then choose or drag several JPEG/PNG/WebP files together. **Start / resume queue** explicitly
starts work. The queue waits for each accepted photo to finish recognition before uploading the next.
Each photo may call the selected model; choosing **Shelf geometry (fast)** and **Don't read (typical prices)**
uses geometry without a VLM and does not identify real product names or measured prices.

- At most 20 files, 25 MiB per file and 100 MiB total in the local queue. Empty/unsupported files are
  rejected with individual messages. Identical bytes already in the queue are skipped even if renamed;
  different photos sharing a filename remain separate. The server independently validates/decodes images.
- Settings and the selected currency stay fixed while files are queued. Clear the local queue to change
  settings. File hashing and stable request IDs require HTTPS or localhost.
- **Pause after current photo** stops later uploads. Remove an unsent entry to skip it. Accepted recognition
  continues on the server; pause, removal, browser navigation and local clearing do not cancel a model call
  or delete a stored capture. The queue remains when reviewing another photo in the same Capture page.
- **Retry this photo** repeats an uncertain upload with the same request identity, or resumes status polling
  without uploading again. If recognition has definitively failed, **Retry recognition (new attempt)** creates
  a new capture and may make new model calls; the failed original is preserved. Resolve an uncertain upload
  or status first before starting a new recognition attempt for another photo.
- Use **Review photo** to correct names, prices, categories and facings. Once reviewed, the existing
  **Combine reviewed shelf photos** flow previews and saves their products/crops/racks in one new layout.

### Save a photo queue and resume later

After choosing photos and settings, select **Save queue on this browser**. This explicitly stores the original
photo bytes, names, recognition settings and stable upload identities in this browser's IndexedDB. It does not
upload photos or start a model. Without a saved copy, keep this page open for unsent files.

1. Return to Capture in the same browser and origin. Use **Continue saved photo queue** (or **Add photos**),
   then **Restore saved queue**. The queue restores paused, without selecting files again. Use
   **Replace local queue from saved copy** only when you want the saved choices to replace your current list.
2. **Start / resume queue** resends the original upload requests. The server returns already accepted captures
   without starting recognition again; previously unsent photos create new captures. Photo bytes may be sent
   again, but accepted jobs are not duplicated. This handles an upload accepted just before its response was
   lost. Recognition progress comes from the server, not the saved browser copy.
3. With recovery enabled, changed queue choices and new recognition-attempt identities are saved before the
   next upload. When paused, use **Save queue on this browser** to retain changed choices before leaving.
   Another tab's changed copy blocks overwriting/resuming: restore the latest copy first.
4. **Forget saved copy** removes only browser recovery, keeping the current queue and uploaded photos.
   **Clear queue and saved copy** removes recovery before clearing the local queue; a storage error leaves
   both intact. Removing individual photos does not delete their accepted server captures.

Recovery uses the same 20-file / 25-MiB-per-file / 100-MiB-total limits. It is local to this browser and site,
not a backup or cross-device sync. Browser quota, eviction, private mode and clearing site data can prevent
or remove recovery. Storage errors preserve the live queue and previous copy. An unreadable/unsupported copy
is not overwritten; browser site-data controls can remove it if needed. Original photos are retained locally
until explicitly forgotten or cleared by the browser. Saved settings are preserved even if project currency
or available models change; an unavailable model may require clearing/reselecting the queue to choose another.
The **App's vision model** choice still refers to the app's current default, which may change between sessions;
select an explicit model before saving when that distinction matters.

Accepted captures remain in history. A restarted single-worker server marks interrupted captures failed,
rather than leaving them pending forever. A retry of a removed accepted photo returns a conflict rather than
recreating it. Clear that local entry and select the file again if you intentionally want a new attempt.

The existing `POST /api/projects/{pid}/captures` endpoint accepts an optional multipart `request_id` of
32 lowercase hexadecimal characters. Retrying the same ID with the same image bytes, filename and normalized
options returns the accepted capture; a changed payload returns 409. Receipts are retained outside removable
capture folders. Failed/interrupted jobs are never automatically re-submitted by replaying an ID. Legacy
uploads without request IDs retain their original behavior.

## Edit placed products together without a spreadsheet

Open a stocked draft layout in the preparation dashboard, then **Step 2: Item placement → Edit products together**.
The editor is available while preparing a layout, not on the run playback screen. Search by product name,
SKU or rack, select individual SKUs or **Select shown**, and set a shared price or promotion. Names can be
edited in their rows. An empty promotion clears it; an empty price is invalid. All placements of an exact
SKU are in scope, including those hidden by your search. Mixed original names/prices remain mixed unless
you change that specific field. SKU identities, shelf positions, images and regular prices stay unchanged.
The current product model has no per-product category field; this editor does not rename rack categories.

1. Make edits in the currency shown. Prices round half up to the currency minor unit (1.005 USD → 1.01 USD;
   1500.5 KRW → 1501 KRW). Zero is allowed only as an explicit input; it is not an inferred missing price.
2. Use **Undo last edit** (last 20 local edit operations) or **Reset unsaved edits** as needed.
3. **Preview product changes** shows actual before/after variants and changed placement counts. Long variant
   lists show the first five and their total count. No-op edits do not create a layout.
4. **Save as new product draft**, then **Open edited layout**. The original is preserved. Return to it from
   Layouts to undo the saved variant; this does not delete either layout.

The catalog accepts up to 5,000 SKUs / 50,000 placements; each save changes at most 500 SKUs. Search displays
up to 100 matching rows at once; narrow your search to reach others. Selected counts include hidden rows.
Prices use nonnegative safe integers in minor units; no FX conversion or model call is made. Template and
user-entered prices are scenario inputs, not verified shelf prices, inventory, margins or sales effects.

A changed source layout or currency rejects preview/save: **Discard edits and reload products**, then review
again. Background catalog refresh does not replace current edits. Closing discards unsaved local inputs;
a save already accepted by the server can finish after you leave. On a connection failure, **Retry saving
product draft** reuses the same request. Check Layouts after leaving before starting another save. An ID
reserved before a failed disk write, or belonging to a removed draft, is not replayed into a replacement;
check Layouts and intentionally start a new preview. Saved request receipts are retained on disk.

API: `GET /api/projects/{pid}/setups/{sid}/product-edits` reads the catalog and snapshot hash.
`POST .../preview` accepts `source_sha256`, `currency`, and unique-SKU `edits` with optional `name`, `price`
and `promo`. `POST .../save` also requires a stable 32-character lowercase hexadecimal `request_id`.
Keep this request unchanged for retries. Product IDs and layouts are never silently merged by name.

## Fill existing empty shelves with starter products

In a draft's preparation dashboard, open **Step 2: Item placement → Auto-place starter products**. This uses the
same generic catalog as store templates while keeping your existing floor, rack positions, signs and
stocked racks. **Automatic by store category** is the default. Add optional assortment requirements and
click **Choose and preview automatically**: the configured text model first chooses categories for the
empty racks, then selects exact existing product IDs within those categories. These are two model requests;
no model is called merely by opening the dialog. Unknown IDs, duplicate selections and incomplete rack
assignments are rejected. Review the products, prices and available images, then **Save stocked layout**.
Automatic selection supports 1–100 empty accessible racks. A failed model call leaves the layout unchanged;
retry or switch to **Choose categories manually**, which needs no model or spreadsheet.

The bundled catalog now includes 1,400 products in 123 categories. New examples cover plant-based foods,
breakfast spreads, home coffee/tea, bath/body care, first-aid tools, supplements, indoor plants, digital
accessories, pet enrichment, picnic reusables, artisan snacks and craft refreshments. Further assortments cover
baking ingredients, global sauces, fresh herbs, frozen and takeaway meals, gift confectionery, baby and oral
care, hair care, travel essentials, sewing, fine art, bicycle accessories, storage, tabletop games and
refill cleaning. Mediterranean, Korean and Japanese pantry staples, spice blends, deli cheeses, fresh seafood,
barista tools and party supplies add another 96 products. Kitchen and baking tools, laundry care, aquarium and small-pet supplies, computer peripherals, camera accessories
and outdoor cookware add another 96 products. Cycling maintenance, swimming, climbing accessories, desk organization, aquarium decor, bird supplies,
home lighting and bathroom accessories add 96 more. Home linens, dinnerware, food storage, pet grooming, hair accessories,
woodcraft, ceramic craft and gift wrapping add another 96. Three hundred fifty-two generated
generic packshots ship locally; they do not require a network connection or image-generation call at use time.
Automatic selection sees which products have photos and prefers them only when they fit the store and
requirements equally well. Products without photos remain available.

Vision shoppers also see available product photos inside their numbered shelf grid, together with the
product name and price. Bundled photos omit empty white margins in this grid so the product itself is larger. This includes bundled catalog images, uploaded SKU photos and reviewed library
photos. Wide assortments wrap within labeled shelf levels so each product stays readable. Missing or
corrupt pictures retain text cards. Shelf-test previews and interview shelf views use the same rendering.
Previously saved starter products also receive newly bundled photos by their exact catalog SKU when no custom
photo is set. Names and prices are preserved, and reading the layout does not rewrite its saved data.
Starter placement previews show these photos too, including current uploads for reused products.
Saving a child layout preserves the reused products’ original labels, prices and stored photo references.
Images are resolved from local project assets; external image URLs are not fetched by the vision renderer.

For manual selection:

1. Search shelves by name or ID. Select individual empty shelves/fridges or **Select shown empty racks**.
   Only racks with no product items anywhere are eligible; a partly stocked rack stays unchanged. Tables
   and checkout counters are excluded. Add an entrance in Step 1 so accessible product faces can be checked.
2. Choose a category per rack, or choose **Category to apply → Apply category to selected racks**. Exact
   catalog keys already stored in rack descriptions provide suggestions; unknown names are not guessed.
   **Reference products** expands the chosen category's examples. Set 1–4 products per shelf section.
3. **Preview starter products** lists each rack, the actual products/prices, new/reused SKU counts and
   added placement counts. All accessible, unlocked faces get four levels; internal/blocked faces stay
   empty. The catalog cycles deterministically through each category, with no duplicate SKU in one section.
4. **Save stocked layout → Open stocked layout** creates and opens a child draft. The original remains
   in Layouts for undo. Use **Edit products together** to correct scenario names, prices and promotions.

Reference products are not actual stock, and reference prices are not observed shelf prices or live FX.
Supported reference currencies are USD, KRW and JPY, using the existing template catalog's illustrative
conversion rules. Other currencies are rejected rather than relabelled. An exact existing catalog SKU
reuses its current name, price, promotion and image link. Conflicting values for the same SKU require
review in the product editor first. Matching names with different SKUs are never silently merged.

Search shows at most 100 racks at once; selections remain across filters. Preview/save accepts at most
100 racks and the resulting layout may have at most 50,000 product placements. Geometry checks allow
up to 65,536 floor cells, 1,000 racks, 10,000 occupied rack cells and 50,000 shape cells. Invalid or
overlapping geometry must be repaired in Step 1. Existing source limits also apply (5,000 SKUs and
50,000 placements). Filling a building floor retains that floor's building metadata.

Changing a selected category or density invalidates the preview. A changed source, currency or bundled
catalog requires **Discard choices and reload** and another review. Unsaved choices live only in the open
dialog. An accepted save may finish after closing. **Retry saving starter draft** reuses the same request
after an uncertain response; check Layouts before starting a new request. A deleted draft or interrupted
write reservation is never silently recreated; intentionally start a new preview after checking Layouts.

API: `GET /api/projects/{pid}/setups/{sid}/starter-fill`, `POST .../auto-select`, `POST .../preview`, `POST .../save`.
Auto-selection takes `source_sha256`, `currency`, optional `requirements`/`model`, and `products_per_slot`;
it returns a preview request whose assignments contain ordered `skus` (1–16 distinct IDs from the category).
Model-selected products are checked again before preview/save, and a changed source invalidates the selection.
Bundled images are served at `/api/catalog-images/{sheet}/{index}.webp` (`starter-01` and `starter-02`, indices 0–15).
The new-store wizard sends `starter_selection: "automatic"` by default; `"format"` uses the original preset
assortment. API clients that omit this field retain the original behavior. Automatic selection groups equivalent
generated racks for large floors, respects excluded categories and product limits, keeps fixture geometry,
and updates shelf signs to match the selected categories. Selected SKU assignments are retained with the initial
layout. The create-store endpoint performs selection off the event loop before creating project files.
Preview takes `source_sha256`, `currency`, unique `assignments` of `rack_id`/`category`, and integer
`products_per_slot` (1–4). Save also takes a stable 32-character lowercase hex `request_id`. Reuse the
identical save body on retry. The snapshot includes the bundled catalog contents as well as the layout.

## Reuse a finished shelf assortment

In a draft's preparation dashboard, open **Step 2: Item placement → Reuse shelf products**. This reuses
products already placed in this layout, whether entered manually, corrected from a reviewed photo or
added from starter products. It does not call a model, create new SKUs or infer physical stock quantities.
Reference/example products remain examples when copied; this operation does not validate their real-world prices.

1. **Copy products from** selects one stocked shelf or fridge. Source products must have valid SKUs and
   safe integer prices, and all occupied faces must be unlocked and reachable from an entrance.
2. Select empty destinations, or **Select shown compatible shelves**. Search by name, identifier or fixture
   type. The list shows up to 100 racks; selected racks remain selected across searches. At most 100
   destinations may be copied in one operation. Stocked racks are protected, even if only partly stocked.
3. **Preview shelf copies** shows each destination, placement totals and the exact source sections, item
   order, names, SKUs, prices, usual prices, promotions and image-link availability.
4. **Save layout with shelf copies → Open copied layout** saves a child draft. The original, stocked racks,
   geometry, descriptions and building-floor context remain unchanged. Use the normal editor or
   **Edit products together** to review the result. Return to the original in Layouts to undo the variant.

Destinations must have the same fixture type and identical *rotated footprint*. Source block indices and
absolute N/S/E/W faces are reused without rotation or mirroring; all copied faces must be accessible and
unlocked at each destination. Every nonempty source section is copied with its original level and item
order. Extra empty destination sections are retained. An incompatible destination rejects the whole batch;
products are never silently truncated to fit. Source product values are copied as stored, including any
intentional repeated SKU placements or different values at different placements. Use the bulk product
editor to review those differences; no deduplication or price harmonization occurs here. Image links/SKU
identity are retained; image files are not duplicated or guaranteed to remain available after later deletion.

The result may have at most 50,000 placements. Source limits are 5,000 distinct SKUs and 50,000 placements;
geometry limits are 65,536 grid cells, 1,000 racks, 10,000 occupied cells and 50,000 shape cells. Repair
invalid geometry or a blocked source in Step 1 before copying.

Source edits/currency changes invalidate an unsaved snapshot. **Discard choices and reload shelves**
resets selections and loads the latest layout, then preview again. A refreshed snapshot cannot relabel an
older price preview. After a failed or uncertain save, **Retry saving shelf copies** keeps the original
request identity and currency so an accepted write can be recovered without another child. Check Layouts
before starting a new request. A removed child or interrupted write reservation is never silently recreated.
Closing discards unsaved choices; an accepted save may finish afterward and remains in Layouts.
Save validates the source snapshot when it reads it; it does not lock the source against other editors.
An edit arriving after that read stays in the original, while the child uses the reviewed snapshot values.

API: `GET /api/projects/{pid}/setups/{sid}/rack-copy` lists stocked sources; optional `source_rack_id`
lists destinations with exclusion reasons. `POST .../preview` takes `source_sha256`, `currency`,
`source_rack_id` and 1–100 unique `target_rack_ids`. `POST .../save` additionally takes a stable
32-character lowercase hex `request_id`. Repeat the identical save body after a lost response.

### Reuse uploaded product photos on a layout

In **Step 2 → Use library photos**, reuse packshots already uploaded in **Market → Products**.
The library's SKU link was previously used for marketing variants; this action applies a reviewed
image to every placement of that exact SKU in a **new layout**.

1. Search shelf products and library photos. **Use unique links for shown products** suggests only
   an existing single SKU link; it does not infer identity from names. Multiple links require a choice.
   Suggestions use all library photos, while each menu shows up to 100 search results plus its selection.
2. Select a photo for each product. Current images are protected by default; enable **Allow replacing
   existing images in the new layout** to change them. Changing this option clears choices.
3. **Preview product photos** shows before/after images and affected placements. Confirm identification
   yourself, especially if a link came from optional model-assisted pack reading.
4. **Save layout with photos**, then **Open photo layout**. Names, prices, promotions, product order,
   geometry and the original layout remain unchanged. Return to the original to undo the variant.

No upload or model call is repeated here. Uploaded reference photos are not proof of actual stock,
price or brand identity. The action does not reconstruct shelf positions or facing counts from a photo.
Saved images are copied into project snapshots and survive later library deletion. A project-wide SKU
image upload does not overwrite these layout-specific images. Snapshot files are retained with the
project, including previews that were not saved, and removed when the project is removed.

Limits: 500 library photos, 100 assigned SKUs per batch, 8 MB per stored photo and 64 MB total selected
photo bytes (counted per assignment). Product layouts support 5,000 SKUs / 50,000 placements. Search
filters keep hidden choices. Empty/unreadable libraries give guidance instead of making up products.
If the layout, its image manifest, or a selected photo/link changes, reload and preview again. A lost
save response can be retried with the same request without duplicating the layout. Closing discards
unsaved choices; an accepted save can finish after closing, so check **Layouts** before starting again.
