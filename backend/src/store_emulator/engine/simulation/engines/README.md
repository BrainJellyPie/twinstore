# Guide to Writing Behavior Engines

> This guide applies when adding a **per-customer engine** (an engine that follows the `CustomerBehaviorEngine` Protocol).

## Overview

An engine decides the **action sequence** for a single customer (where to visit and what to do).
Path calculation (A*) and timeline conversion are handled by the shared executor, so the engine only needs to focus on deciding behavior.

```
┌─────────────────────────┐
│  Engine (your code)     │
│  decide_actions()        │
│  → list[CustomerAction]  │
└────────────┬────────────┘
             ↓
┌─────────────────────────┐
│  Shared executor (auto) │
│  build_journey()         │  ← A* path calculation + action correction
│  build_timeline()        │  ← convert to chronological timeline
│  → CustomerResult        │
└─────────────────────────┘
```

## Folder structure

```
engines/
├── __init__.py                    ← engine registry (EngineType → module/class mapping)
├── rule_based.py                  ← heuristic engine, no LLM (single file)
├── vlm_glance/                    ← vision-language shopper (rule planner + VLM impulse)
└── pattern_intent_impulse/        ← PII engine (subpackage, uses LLM)
    ├── __init__.py                ← PatternIntentImpulseEngine export
    ├── engine.py                  ← engine body
    ├── stage1_pattern.py          ← prompt: pattern selection
    ├── stage2_intent.py           ← prompt: intent generation
    ├── stage3_impulse.py          ← prompt: impulse response
    └── prompt_utils.py            ← shared prompt utilities
```

Simple engines go in a single file; engines with many supporting files (prompts, etc.) use a subpackage.

## Prerequisites

- **Coordinate system**: `(x, y)` — x = column (horizontal), y = row (vertical). Grid access is `grid[y][x]`
- **Price unit**: minor units of `SimulationConfig.currency` (USD cents by default: 100 = $1.00; KRW: whole won). `Slot.price` and `Persona.budget_min/max` all use the same unit. Prompts should describe prices with `engine/prompting.py` (`price_unit_rule`, `format_price`, `format_budget`) rather than hard-coding cents
- **Randomness**: draw only from `random.Random(context.seed)` (or seeds derived from it). Never use the global `random` module or an unseeded `Random()` — that breaks reproducibility and the paired (common-random-numbers) layout comparison
- **Time unit**: dwell and all other time-related values are in seconds
- **Time format**: `"HH:MM:SS"` string (e.g. `arrival_time`)
- **async required**: `decide_actions` is an async method. Declare `async def` even if you don't use LLM
- **Grid size**: default max 30×30. `store.grid_size` is a `(width, height)` tuple

## Engine interface

Follow the Protocol defined in `domain/engine.py`:

```python
class CustomerBehaviorEngine(Protocol):
    engine_type: str

    async def decide_actions(
        self, context: PerCustomerContext,
    ) -> EngineDecision: ...

    def reset_usage(self) -> None: ...
    def get_usage(self) -> TokenUsage: ...
```

### Input: PerCustomerContext

Constructed per customer and passed to the engine. The engine only needs to use the fields it cares about.

| Field | Type | Description |
|-------|------|-------------|
| `store` | `Store` | Full store info (grid, racks, products, entrance/exit, counter) |
| `persona` | `Persona` | Customer profile (identity, age, gender, purpose, budget, etc.) |
| `day` | `Weekday` | Simulation day (MON=1 ~ SUN=7) |
| `arrival_hour` | `int` | Arrival time (0–23) |
| `concurrent_visitors_in_hour` | `int` | Number of other customers arriving in the same hour (congestion reference) |
| `cue` | `BehaviorCue` | Individual behavior variation seed (state/purse/emotion/company) |
| `behavior_patterns` | `list[BehaviorPattern]` | Available behavior patterns |
| `address`, `customer_profile` | `str` | Project context (may be empty) |
| `seed` | `int` | Per-customer seed from `(run seed, replicate, persona id)`; identical across layouts |

### Output: EngineDecision

```python
class EngineDecision(BaseModel):
    actions: list[CustomerAction]  # action sequence (required)
    engine_type: str               # engine identifier (required)
    trace: dict[str, object] = {}  # debug log (optional, not persisted)
    dropped_invalid_buys: int = 0  # BUYs removed because the SKU is not in the store
    dropped_over_budget: int = 0   # impulse BUYs removed by the budget tolerance
```

`trace` is not saved to `CustomerResult`. The `customer_executor` logs only the key names at DEBUG level.
The two `dropped_*` counters are copied to `CustomerResult` and summed in `diagnostics.json`.

### Token usage

- LLM engines: delegate `reset_usage()`/`get_usage()` to `LiteLLMClient`
- Non-LLM engines: no-op `reset_usage()` + `get_usage()` that returns `TokenUsage()`
- The Simulator calls these at the start and end of a run and records results in `AggregatedResult.token_usage`

## Writing CustomerAction

The unit of action returned by the engine. The shared executor converts these into physical paths.

```python
class CustomerAction(BaseModel):
    nav: "path" | "area" | "leave"    # movement mode
    target: tuple[int, int] | None    # destination coordinate (when nav="path")
    face: Face | None                 # rack approach direction (N/S/E/W)
    action: Action | None             # ENTER/BROWSE/BUY/WANDER/PAY/EXIT
    dwell: int = 0                    # dwell time (seconds)
    product_sku: str = ""             # product SKU for BUY
    quantity: int = 1                 # units for BUY (clamped to max_quantity_per_line)
    origin: str = "planned"           # "planned" | "impulse" (not part of the LLM schema)
    description: str = ""            # action description (optional)
    area: tuple[x1,y1,x2,y2] | None  # WANDER area (when nav="area")
```

Set `origin="impulse"` on BROWSE/BUY actions the customer did not plan; the
aggregator uses it for impulse revenue/unit share. `origin` is hidden from the
JSON schema sent to LLMs (`SkipJsonSchema`), so engines set it in code.

### nav mode usage

| nav | Purpose | Required fields |
|-----|---------|-----------------|
| `"path"` | Move to a specific coordinate | `target` |
| `"area"` | Wander within a region | `area`, `dwell` |
| `"leave"` | Exit the store (move to exit) | none |

### Typical action sequence

```python
from store_emulator.engine.routing.route_builder import entrance_position

entrance = entrance_position(store)
rack = store.product_racks[0]
rack_access = list(rack.access_tiles(store.grid_size))[0]
counter_access = list(store.counters[0].service_access_tiles(store.grid_size))[0]

[
    CustomerAction(nav="path", target=entrance, action=Action.ENTER, dwell=2),
    CustomerAction(nav="path", target=rack_access, face=rack.slots[0].face, action=Action.BROWSE, dwell=5),
    CustomerAction(nav="path", target=rack_access, face=rack.slots[0].face, action=Action.BUY, dwell=3, product_sku=rack.slots[0].sku),
    CustomerAction(nav="path", target=counter_access, action=Action.PAY, dwell=15),
    CustomerAction(nav="leave", action=Action.EXIT),
]
```

### Required rules

- Must start with **ENTER**. It becomes the first event in the timeline.
- Must end with **EXIT** (`nav="leave"`). If omitted, there will be no exit event.
- **PAY** only when there is a BUY. PAY can be omitted in scenarios with no purchase.
- Returning an empty actions list results in an empty timeline — include at least ENTER + EXIT.

### target coordinate correction

Even if `target` is not exact, the shared executor corrects it automatically:
- Coordinates on a wall/rack → corrected to the nearest walkable tile
- PAY action → forced to the counter's `service_access_tile`

## Key model fields in context

### Persona (customer profile)

```python
persona.id                    # unique ID
persona.identity              # e.g. "office worker", "college student"
persona.age_group             # e.g. "teens" ~ "60s+"
persona.gender                # "M" | "F"
persona.purpose               # visit purpose (e.g. "grab lunch", "browse")
persona.preferred_categories  # preferred categories ["drinks", "snacks"]
persona.budget_min / max      # budget range (cents)
persona.behavior_tendency     # behavior tendency text
persona.arrival_hour          # arrival time (0–23)
```

### BehaviorPattern

```python
pattern.id                        # "purposeful", "exploratory", etc.
pattern.name                      # display name
pattern.grammar                   # behavior grammar text for LLM prompt
pattern.max_products              # max products to purchase
pattern.allow_no_purchase         # whether zero-purchase is allowed
pattern.browse_required_before_buy  # whether browsing is required before buying
```

### BehaviorCue (individual variation seed)

```python
cue.state     # condition — e.g. "tired", "hungry", None
cue.purse     # spending mindset — e.g. "value-seeking", "splurging", None
cue.emotion   # mood — e.g. "happy", "irritated", None
cue.company   # companion — e.g. "alone", "with friends", "with kids"
```

## Useful data access from Store

```python
store.grid_size          # (width, height)
store.racks              # all racks (walls, entrance, exit included)
store.product_racks      # only racks with products (property)
store.counters           # counter racks only (property)
store.entrances          # entrance racks (property)
store.exits              # exit racks (property)
store.walkable_grid()    # bool 2D grid (True = walkable)
context.address          # store address (passed via PerCustomerContext)
context.customer_profile # customer profile (passed via PerCustomerContext)

# Rack access
rack.slots               # products placed in the rack (Slot: sku, name, price, face, level)
rack.access_tiles(store.grid_size)      # set of tile coordinates the customer can approach from
rack.type                # RackType (SHELF, FRIDGE, COUNTER, ENTRANCE, EXIT)
rack.occupied_positions  # grid coordinates occupied by this rack

# Shared infrastructure (call as read-only)
from store_emulator.engine.routing.route_builder import entrance_position, build_journey, find_exposed_products
```

## Adding a new engine

### 1. Implement the engine

Create a file or subpackage in `engines/`:

```python
# engines/my_engine.py (simple case)

from store_emulator.domain.engine import PerCustomerContext, EngineDecision
from store_emulator.domain.types import TokenUsage

class MyEngine:
    engine_type = "my_engine"

    def reset_usage(self) -> None:
        pass

    def get_usage(self) -> TokenUsage:
        return TokenUsage()

    async def decide_actions(self, context: PerCustomerContext) -> EngineDecision:
        actions = ...  # behavior decision logic
        return EngineDecision(actions=actions, engine_type=self.engine_type)
```

LLM-based engines should be structured as a subpackage (like `pattern_intent_impulse/`)
and delegate `reset_usage()`/`get_usage()` to `LiteLLMClient`.

### 2. Register the EngineType

`domain/config.py`:

```python
class EngineType(StrEnum):
    PATTERN_INTENT_IMPULSE = "pattern_intent_impulse"
    MY_ENGINE = "my_engine"  # add
```

### 3. Register in the registry

`engines/__init__.py`:

```python
ENGINES: dict[EngineType, tuple[str, str, bool]] = {
    EngineType.PATTERN_INTENT_IMPULSE: (".pattern_intent_impulse", "PatternIntentImpulseEngine", True),
    EngineType.MY_ENGINE: (".my_engine", "MyEngine", False),  # add
}
```

The third value (`bool`) indicates whether an LLM client is required. If `True`, the factory creates and injects a `LiteLLMClient`
(`engine_cls(llm=..., pathfinder=..., config=...)`); otherwise it calls `engine_cls(pathfinder=..., config=...)`.
The new engine then appears in `GET /api/engines`, the UI run launcher and `parastore --engine`.

### 4. Verify

```bash
uv run pyright src/   # type check 0 errors
```

## Reference: existing engines

| Engine | Location | Paradigm | Characteristics |
|--------|----------|----------|-----------------|
| `pattern_intent_impulse` | `engines/pattern_intent_impulse/` | per-customer | 3-stage LLM pipeline: pattern selection → intent generation → impulse response. Exposure is computed on the planned route (`perceive_products`, visibility scores passed to stage 3). Stage 2 uses a store-level cacheable system prompt |
| `rule_based` | `engines/rule_based.py` | per-customer | No LLM. Pattern draw, category-matched planned buys, visibility-driven impulse buys and browse-only stops. Parameters in `RuleBasedConfig`; deterministic given `context.seed` |
| `vlm_glance` | `engines/vlm_glance/` | per-customer | `RuleBasedEngine` planner + VLM impulse step: renders each well-seen rack face (`engine/perception/shelf_render.py`) and asks a vision model what catches the persona's eye. Config in `VLMGlanceConfig`; exports every glance through `metadata()` |

### Reusing the rule-based planner

`RuleBasedEngine.decide_actions` is `_plan()` → `await _impulse()` → `_finish()`.
Subclass it and override only `_impulse(context, plan)` to change how unplanned
purchases happen; use `can_buy_more`, `add_impulse_buy` and `add_impulse_look`
so budget, item caps and action shapes stay identical across engines.

### Run-level metadata

An engine that implements `metadata() -> dict[str, object]`
(`domain.engine.EngineMetadataSource`) gets it saved as
`output/<engine_type>_meta.json` by the server and the CLI.

### Exposure helpers

`engine/routing/route_builder.py` exposes what an engine needs to reason about
what a customer can see:

- `perceive_products(store, journey, config.perception)` → `list[ExposedProduct]`
  (`rack`, `slot`, `sku`, `visibility` in (0, 1], `facings`) for a walked path
  (`journey` from `build_journey`).
- `integrate_actions(store, intent_actions, impulse_actions, ordering=config.route_ordering)`
  merges impulse visits into a planned route (`"planned"` = keep the shopper's
  order and insert impulse racks at the cheapest detour, `"nearest"` = legacy
  greedy re-ordering).

## Files not to modify

When adding an engine, do not touch the following files:
- `engine/simulation/simulator.py` — `PerCustomerSimulationRunner` (receives engine by injection only)
- `engine/simulation/customer_executor.py` — shared executor
- `engine/simulation/factory.py` — auto-loads from the registry
- `engine/routing/*` — path calculation infrastructure
