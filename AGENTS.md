# AGENTS.md — TwinStore

Conventions and orientation for AI coding agents (Claude Code, Cursor,
Codex, Aider, …) working in this repository. Human contributors should also
find it useful.

> **Helping an end user run parastore rather than modify the code?** See
> [`USAGE.md`](./USAGE.md) instead — it covers the wizard inputs, LLM
> call counts per persona size, supplemental-file conventions, and the
> silent-failure modes to coach the user through before triggering a
> simulation.

## What this project is

TwinStore (built on intellicia's open-source Parastore) is a store digital twin:
an isometric 3D store-layout simulator with LLM/VLM-driven virtual personas. See [`README.md`](./README.md) for the user-facing description and
local-run instructions; this file covers everything you need to make a clean
contribution.

## Repo layout

```
parastore/
  backend/   — Python 3.13+ FastAPI + LiteLLM + Instructor + pathfinding
  frontend/  — Vite + React 19 + R3F (Three.js) + Zustand + Tailwind v4 + shadcn/ui + Recharts
  launcher/  — Go one-click launcher (TwinStore.exe / TwinStore.app / twinstore), icon, release build
  scripts/   — dev/build helper scripts
```

Internal identifiers keep the original `parastore` prefix for compatibility (`PARASTORE_*`
environment variables, browser storage keys, the repository name); user-facing text says TwinStore.

Local run: `./scripts/dev.sh` (see README for prerequisites).

## Verification commands

Run these before claiming a change is done:

```bash
# Backend type check (strict mode — keep zero errors)
cd backend && uv run pyright src/

# Backend boot smoke
cd backend && uv run python -c "from store_emulator.server.main import app; print('OK')"

# Backend tests
cd backend && uv run pytest

# Frontend build (also runs tsc)
cd frontend && pnpm build

# Frontend lint
cd frontend && pnpm lint

# Frontend tests
cd frontend && pnpm test
```

## Backend architecture

Strict layered dependency direction:

```
domain ← engine ← application ← server
```

No reverse dependencies.

- **`domain/`** — pure data models (Pydantic) and `Protocol` definitions.
  No I/O, no prompts, no framework imports.
- **`engine/`** — implementations of `domain` Protocols. LLM pipelines,
  pathfinding, simulation engines.
- **`application/`** — use-case wiring, presets, storage.
- **`server/`** — FastAPI routers and schema conversion. The only layer
  that touches HTTP.

When in doubt about where new code belongs, ask "what is the lowest layer
that has all the imports I need?" and put it there.

## Backend code conventions (Python)

- `pyright` strict mode — keep zero errors.
- No `Any`. Repeated structural types live in `domain/types.py`
  (e.g. `Position`, `Shape`).
- No incomplete generics — write `dict[str, object]`, `list[int]`, etc.
- `type: ignore` only at third-party boundaries, with a comment explaining
  why.
- No abbreviated imports — use the full module path.
- When adding a dependency, pin a lower bound to the latest stable PyPI
  version in `backend/pyproject.toml`.
- Don't introduce wrapper classes or single-use utilities. If
  de-duplication hurts readability, allow the duplication.
- Logging uses module-level `logger = logging.getLogger(__name__)`. Log in
  English.

## Frontend code conventions

- TypeScript strict, ESLint with the React Compiler plugin enabled —
  `pnpm lint` clean.
- Routing: TanStack Router (`src/routes/`, code-split via
  `src/routeTree.gen.ts` — the snapshot ships a committed copy so a fresh
  `pnpm build` works without the dev plugin running first).
- Data fetching: TanStack Query against the FastAPI backend; mutations and
  queries colocated under `src/services/{queries,mutations}/`.
- State: Zustand stores in `src/stores/` (one store per concern — playback,
  simulation metrics, simulation lifecycle).
- Feature folders under `src/features/` are self-contained
  (`{capture,dashboard,grid-editor,layouts,marketing,playback,setup,store-viewer,town,…}`); shared
  primitives go in `src/shared/`.
- 3D rendering uses React Three Fiber (`@react-three/fiber` + `drei`) with
  isometric camera; GLB assets live under `public/assets/{market,characters,ghost}/`
  and are mapped in `shared/utils/assetMap.ts`.
- UI: shadcn/ui + Radix primitives + Tailwind v4. Icons from
  `lucide-react`, charts from Recharts, Excel exports via `exceljs` /
  `xlsx`.

## i18n policy

Frontend display text can be localized through `frontend/src/shared/i18n/`. The language
picker supports English, Korean, Chinese, Japanese, Spanish and French. All new end-user UI copy
must use this catalog, including explanations, accessibility names, validation and save/error states.
Existing coverage includes the home,
main navigation, command palette, store gallery, model notice, simulation launcher, new-store forms,
preparation/recovery screens, layout navigation/finder, basic layout-creation forms, floor-plan import and template
search/filter controls, reviewed library-photo reuse, product bulk editing, shelf-product reuse and automatic/manual starter filling (including catalog categories), and floor-plan previews/comparisons with localized SVG exports (keys in the main catalog, `plan*`). Store-category labels are shared between the gallery and template picker. The layout
customization panel (patterns, entrances, counters, seating, design and colors, hours, categories, reserved areas,
options files) and building floors and presets use keys in `messages/layout.ts`; option ids stay unchanged and
preset floor labels are ordinary editable text. Persona age groups and genders read through
`shared/i18n/personaLabels.ts` everywhere (the values `40s`, `Female` are unchanged).
The marketing studio (every tab, builder and report), shelf capture with Shelf Lab and the neighborhood
(area) page are localized too, with keys in `messages/studio.ts`. Their server-generated notes, warnings,
rationale and audit/CSV exports stay English, and persona quota values (`10s`, `Female`) and the A/B control arm
name (`Control`, shown translated) are sent unchanged.
The main store screen is localized with keys in `messages/store.ts`: the playback panel, compass, realistic-view
and photo-mode controls, the Results/Shoppers/Store tabs (live dashboard, run KPIs and segments, run analyst,
diagnostics and validation sections, shopper list, journey, interviews), the run toolbar, run names, the Compare
and Optimize dialogs, the situation editor, item-placement dialogs and the floor editor; so are Settings
(model providers, the local vision model) and store-format names (`tpl_<template id>`, ids unchanged; English shows
the server's name). Sample stores whose type is an English category label (`Convenience store`) use the shared
store-category labels. Server-written text (analyst answers, run/optimizer notes, scenario preset names, persona
fields, model replies and errors) stays as sent; only the no-situation `baseline` preset reads as the translated
ordinary day. `richText()` puts bold figures or code into a translated sentence;
`timeFormat.ts` gives weekday names and store clocks in the selected language.
Coverage is still being audited; a catalog entry alone does not prove every state is localized.
Add translations in all six columns
when extending these surfaces. Use the selected locale for dates and numbers.
Prefer natural task-oriented copy over word-for-word translation; follow
[`verification/i18n-copy-style.md`](./verification/i18n-copy-style.md) for language-specific voice.
Interior design names are shared by setup, floor review and comparison; color resets use complete
localized messages, and preview failures retain diagnostics below localized recovery guidance.
Operating-hour, assortment-limit/seed and options-file controls also use the catalog; known product
category labels are shared across the starter-fill and template flows.

Backend logs, errors and FastAPI OpenAPI metadata remain English. Keep API identifiers,
status values, dict keys, `===` comparisons and route params unchanged when translating display
text. Localized labels must never become frontend/backend contract values.

Apart from the frontend translation catalog and its tests, Korean strings are intentional
and confined to LLM-internal sites or compatibility values. The categories are:

- **Prompt bodies / prompt-composing fragments** — the prompts were tuned
  in Korean by native speakers; rewriting them risks behavior regressions.
  Each prompt template carries a `## 언어` directive instructing the model
  to emit narrative output fields in English. Files involved:
  `engine/generators/persona.py`,
  `engine/simulation/engines/pattern_intent_impulse/{stage1_pattern,stage2_intent,stage3_impulse,prompt_utils}.py`,
  `application/supplemental.py`,
  `application/presets/behavior.py`,
  `domain/types.py` (`WEEKDAY_LABELS` — only consumed by prompt builders).
- **Korean Literal types** kept for backwards-compatible match sites:
  `domain/persona.py` (`Gender = Literal["남", "여"]`,
  `AgeGroup = Literal["10대", ...]`) and the matching comparison site in
  `frontend/src/shared/utils/assetMap.ts`.

If you add a new prompt template, follow the pattern in
`engine/generators/persona.py` (`PERSONA_PROMPT`): include a `## 언어`
block listing which output fields should be emitted in English. If you need
to add new structured Korean Literal values, prefer English values for new
code instead.

## Practical notes

- LLM calls cost money. Avoid running the full simulation pipeline in
  smoke tests. The `analyze_*` and `generate_*` functions in
  `engine/generators/` are the expensive ones.
- `backend/.data/` is a local-only artifact directory (gitignored). Do not
  commit anything from it.
- `.env` files are gitignored. Use `backend/.env.example` as the template.
- Prompts live in module-level constants named `*_PROMPT`. Search by that
  suffix to find them.

## Scope discipline

When fixing a bug or adding a small feature, change only what the task
requires. Don't introduce abstractions for hypothetical future
requirements, don't add error handling for paths that can't happen, don't
add comments that restate the code, and don't reformat unrelated regions.
A small, focused diff is much easier to review and revert.
