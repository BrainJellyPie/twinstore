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

The wizard collects two screens of input, then kicks off an async pipeline:

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
                 # customer; with the default gating about 1–1.5.

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
the complete plan has 40–10,000. This is a fixed sample target chosen by the operator, not a power calculation.
The product, price, scripts, context, eligibility, window, seed and allocations are saved and cannot be edited.
No model calls are needed to create or analyze a field pilot from a saved screening report.

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

Upload the **full** UTF-8 CSV (up to 2 MB), retaining every row and assignment column. Uploads replace the previous
observation sheet atomically; invalid rows, changed assignments, duplicates and omitted rows reject the whole file.
Revision checks and file locks reject overlapping updates; reload before retrying a stale upload. Downloading the
sheet again returns the current observations, so corrections can be made before closing.

During collection, the dashboard shows recorded rates and worst/best missing-outcome bounds over enrolled
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
- **Layout is a separate step.** Finishing the wizard creates a project
  with no store layout. Simulation cannot run until the user builds a
  grid in the layout editor (`/features/grid-editor/`).
- **Hidden inputs not exposed in the wizard**: `custom_instruction` and
  `max_persona_count_per_day` are accepted by the regenerate API
  (`backend/src/store_emulator/application/generation_async.py`) but
  have no UI yet. If the user asks how to constrain persona generation
  further, these are the levers.
- **Choosing the LLM provider.** Default model is
  `gemini/gemini-3.1-pro-preview` (`LLMConfig.model` in
  `backend/src/store_emulator/application/config.py`). Filling in
  `OPENAI_API_KEY` or `ANTHROPIC_API_KEY` alone has no effect — set
  `PARASTORE_LLM_MODEL` to the matching LiteLLM model string *and* the
  matching `*_API_KEY` in `backend/.env`. For a self-hosted
  OpenAI-compatible server also set `PARASTORE_LLM_API_BASE`
  (e.g. `PARASTORE_LLM_MODEL=openai/local`,
  `PARASTORE_LLM_API_BASE=http://127.0.0.1:8080/v1`). Small local models
  (≤4B) tend to fail the structured stage-2 output on large catalogs; use
  `rule_based` for local-only setups.
- **`PERSONA_DAILY_CAP` env var** (default `100`) caps the per-day slice
  used when `max_persona_count_per_day` is supplied: the requested total
  is divided across open days, then clamped to `[10, PERSONA_DAILY_CAP]`
  in multiples of 10. Raise it if a single day legitimately needs more
  than 100 personas.
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
