# USAGE.md — Parastore

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

Source: `backend/src/store_emulator/engine/generators/persona.py:99-242`,
`backend/src/store_emulator/engine/simulation/engines/pattern_intent_impulse/engine.py:56-119`,
`backend/src/store_emulator/application/supplemental.py:214-499`.

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
