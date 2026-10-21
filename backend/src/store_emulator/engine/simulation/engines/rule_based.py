"""Rule-based shopper engine — a fast, LLM-free baseline.

Why it exists:
- Research: every claim about the LLM engine needs a cheap baseline it must beat.
- Product: instant "preview" runs for layout iteration without LLM cost or latency.
- Engineering: deterministic end-to-end tests of the whole pipeline.

Behavior (all knobs live in `RuleBasedConfig` and are meant to be calibrated):
1. Draw a behavior pattern from `pattern_weights`.
2. Turn each preferred category into a planned purchase by matching category
   words against rack names/descriptions and product names; pick the item by
   shelf-level attention, price fit with the remaining budget and promotions.
3. Walk the planned route, perceive products with the visibility model, and
   buy unplanned items with probability impulse_base × visibility × modifiers.
"""

import math
import random
import re
from dataclasses import dataclass, field

from store_emulator.domain.action import CustomerAction
from store_emulator.domain.behavior import BehaviorPattern
from store_emulator.domain.config import SimulationConfig
from store_emulator.domain.engine import EngineDecision, PerCustomerContext
from store_emulator.domain.rack import Rack, Slot, SlotItem
from store_emulator.domain.store import Store
from store_emulator.domain.types import (
    Action,
    PathFinder,
    Position,
    TokenUsage,
    stable_seed,
)
from store_emulator.engine.routing.route_builder import (
    build_journey,
    entrance_position,
    face_access_tile,
    integrate_actions,
    perceive_products,
)
from store_emulator.engine.scenario import (
    ScenarioEffects,
    compile_scenario,
    hour_effects,
    item_categories,
    priors_for,
    words_categories,
)

# Category word → related words found on rack labels / product names. Deliberately
# small and bilingual (English + Korean store labels); unmatched categories fall
# back to an exploratory pick.
_SYNONYMS: dict[str, set[str]] = {
    "drink": {"drink", "beverage", "soda", "juice", "tea", "coffee", "water", "energy", "milk", "latte",
              "음료", "커피", "차", "주스", "생수", "우유", "탄산"},
    "snack": {"snack", "chip", "candy", "chocolate", "cookie", "sweet", "confectionery", "cracker",
              "과자", "스낵", "사탕", "초콜릿", "젤리"},
    "food": {"food", "meal", "ready", "ramen", "noodle", "sandwich", "lunch", "rice", "soup",
             "도시락", "김밥", "라면", "식품", "간편식", "샌드위치"},
    "bakery": {"bakery", "bread", "bun", "muffin", "donut", "pastry", "빵", "베이커리"},
    "frozen": {"frozen", "ice", "cream", "dessert", "popsicle", "아이스크림", "냉동", "디저트"},
    "dairy": {"dairy", "milk", "yogurt", "cheese", "유제품", "요거트", "치즈"},
    "health": {"health", "wellness", "beauty", "care", "vitamin", "건강", "의약", "생활용품"},
    "alcohol": {"beer", "wine", "soju", "alcohol", "liquor", "주류", "맥주", "소주", "와인"},
}

PATTERN_IMPULSE_FACTOR: dict[str, float] = {
    "impulse_heavy": 2.5, "social_browsing": 1.6, "leisurely": 1.4, "exploratory": 1.3,
    "hungry_wandering": 1.2, "deal_hunting": 1.0, "purposeful": 0.8, "habitual": 0.6,
    "routine_refill": 0.6, "quick_snack": 0.5, "urgent": 0.25, "window_shopping": 0.0,
}

_WANDERING_PATTERNS = {"exploratory", "leisurely", "social_browsing", "hungry_wandering", "window_shopping"}


def tokenize(text: str) -> set[str]:
    """Lower-cased words without pure numbers, crudely singularized ("chips" → "chip")."""
    out: set[str] = set()
    for raw in re.split(r"[^\w]+", text.lower()):
        if not raw or raw.isdigit():
            continue
        out.add(raw[:-1] if len(raw) > 3 and raw.endswith("s") else raw)
    return out


def expand_category(category: str) -> set[str]:
    """Category words plus the synonym groups they touch ("coffee" → every drink word)."""
    words = tokenize(category)
    expanded = set(words)
    for key, group in _SYNONYMS.items():
        if words & group or key in words:
            expanded |= group | {key}
    return expanded


@dataclass
class ShopperPlan:
    """State shared by the planning, impulse and finishing steps of one customer."""
    pattern: BehaviorPattern
    rng: random.Random
    grid: list[list[bool]]
    budget: int
    tolerance: float | None
    spend: int
    walk_out: bool
    buys: list[CustomerAction]
    chosen: set[str]
    planned: list[CustomerAction]
    # False: the shopper turned around at the door (no impulse step, no purchase).
    entered: bool = True
    hour: int = 12   # arrival hour: part-of-day demand (ScenarioEffects.hour_for)
    trace: dict[str, object] = field(default_factory=dict[str, object])


@dataclass
class ImpulseOutcome:
    actions: list[CustomerAction] = field(default_factory=list[CustomerAction])
    buys: int = 0
    looks: int = 0
    trace: dict[str, object] = field(default_factory=dict[str, object])


class RuleBasedEngine:
    """Planning (steps 1–2) and the impulse step (3) are separate methods so other engines
    can keep this planner and replace only how impulse decisions are made (see vlm_glance)."""

    engine_type = "rule_based"

    def __init__(self, pathfinder: PathFinder, config: SimulationConfig):
        self._pathfinder = pathfinder
        self._config = config
        self._fx = compile_scenario(config.scenario, config.scenario_priors) if config.scenario is not None else ScenarioEffects()
        # Tokenized catalog per store object (one store per run; a run calls us per customer).
        self._catalog: tuple[Store, list[tuple[Rack, Slot, SlotItem, set[str], set[str]]]] | None = None

    def _catalog_for(self, store: Store) -> list[tuple[Rack, Slot, SlotItem, set[str], set[str]]]:
        if self._catalog is None or self._catalog[0] is not store:
            entries = [
                (rack, slot, item, tokenize(f"{rack.rack_name} {rack.rack_desc}"), tokenize(item.name))
                for rack in store.product_racks for slot in rack.slots for item in slot.items
            ]
            self._catalog = (store, entries)
        return self._catalog[1]

    def reset_usage(self) -> None:
        pass

    def get_usage(self) -> TokenUsage:
        return TokenUsage()

    def prepare(self, store: Store) -> None:
        """Called once per run with the store: situation and part-of-day effects follow the store's format."""
        priors = priors_for(store.type, self._config.scenario_priors)
        if self._config.scenario is not None:
            self._fx = compile_scenario(self._config.scenario, priors)
        else:
            self._fx = hour_effects(priors)

    def _demand(self, categories: set[str], hour: int) -> float:
        """Situation × part-of-day demand multiplier, clipped to [0.2, 3]."""
        return min(3.0, max(0.2, self._fx.demand_for(categories) * self._fx.hour_for(hour, categories)))

    async def decide_actions(self, context: PerCustomerContext) -> EngineDecision:
        plan = self._plan(context)
        impulse = await self._impulse(context, plan)
        return self._finish(context, plan, impulse)

    def _plan(self, context: PerCustomerContext) -> ShopperPlan:
        """Rule plan: walk-out draw and one planned purchase per matched preferred category, both
        scaled by the scenario's numeric demand / walk-out multipliers."""
        params = self._config.engines.rule_based
        store, persona = context.store, context.persona
        plan, middle = self._begin_plan(context)
        pattern, rng = plan.pattern, plan.rng
        plan.walk_out = pattern.allow_no_purchase and rng.random() < min(0.9, params.walkout_prob * self._fx.walkout)
        target = persona.basket_size if persona.basket_size > 0 else pattern.max_products
        usual = frozenset(p.lower() for p in persona.usual_products)
        kinds = persona.basket_kinds if persona.basket_size > 0 else 0
        used: list[str] = []   # categories in the basket, for a trip of known breadth (basket_kinds)
        if pattern.max_products > 0 and not plan.walk_out:
            for position, category in enumerate(persona.preferred_categories):
                if len(plan.buys) >= target or (kinds and len(used) >= kinds):
                    break
                # Lists are written in priority order: later entries are less likely to be bought.
                hit_prob = (params.planned_hit_prob * params.plan_position_decay ** position
                            * self._demand(words_categories(category), plan.hour) ** 0.5)
                if rng.random() > min(0.98, hit_prob):
                    continue
                pick = self._pick_item(store, category, plan.budget - plan.spend, plan.chosen, rng, usual)
                if pick is None:
                    continue
                rack, slot, item = pick
                self.add_planned_buy(store, plan, middle, rack, slot, item, f"looks for {category}")
                used.append(category)
                # More products from the same category (several flavours, sizes): geometric extras
                # with mean items_per_category − 1. Drawn only when calibrated above 1.
                extra_p = 1.0 - 1.0 / params.items_per_category
                while (extra_p > 0 and len(plan.buys) < target and rng.random() < extra_p):
                    more = self._pick_item(store, category, plan.budget - plan.spend, plan.chosen, rng, usual)
                    if more is None:
                        break
                    self.add_planned_buy(store, plan, middle, *more, f"also takes more {category}")
            if persona.basket_size > 0:
                self._fill_to_size(store, plan, middle, persona.preferred_categories, target, usual, kinds, used)
        return self.close_plan(store, plan, middle)

    def _fill_to_size(self, store: Store, plan: ShopperPlan, middle: list[CustomerAction],
                      categories: list[str], target: int, usual: frozenset[str] = frozenset(),
                      kinds: int = 0, used: list[str] | None = None) -> None:
        """A trip of known size: keep taking products from the list (in priority order, round after
        round) until the basket has `target` products, the list is exhausted or money runs out. With
        `kinds`, a new category is opened only while the basket spans fewer than `kinds` of them."""
        used = used if used is not None else []
        while len(plan.buys) < target:
            progressed = False
            for category in categories:
                if len(plan.buys) >= target:
                    return
                if kinds and category not in used and len(used) >= kinds:
                    continue
                pick = self._pick_item(store, category, plan.budget - plan.spend, plan.chosen, plan.rng, usual)
                if pick is not None and self.add_planned_buy(store, plan, middle, *pick, f"also needs {category}"):
                    progressed = True
                    if category not in used:
                        used.append(category)
            if not progressed:
                return

    def _begin_plan(self, context: PerCustomerContext) -> tuple[ShopperPlan, list[CustomerAction]]:
        """Pattern draw, budget and the wandering stop: everything a plan has before its purchases.
        Returns the plan (no route yet) and the list of in-store actions to extend."""
        cfg = self._config
        store, persona = context.store, context.persona
        rng = random.Random(stable_seed(context.seed, "rule_based"))
        pattern = self._pick_pattern(context.behavior_patterns, rng, persona.basket_size)
        middle: list[CustomerAction] = []
        if pattern.id in _WANDERING_PATTERNS:
            w, h = store.grid_size
            middle.append(CustomerAction(
                nav="area", area=(1, 1, max(1, w - 2), max(1, h - 2)),
                action=Action.WANDER, dwell=rng.randint(20, 60), description="wanders the aisles",
            ))
        plan = ShopperPlan(
            pattern=pattern, rng=rng, grid=store.walkable_grid(),
            budget=persona.budget_max if persona.budget_max > 0 else 10**9,
            tolerance=cfg.budget_tolerance, spend=0, walk_out=False, buys=[], chosen=set(), planned=[],
            hour=context.arrival_hour,
        )
        return plan, middle

    def add_planned_buy(
        self, store: Store, plan: ShopperPlan, middle: list[CustomerAction],
        rack: Rack, slot: Slot, item: SlotItem, why: str, *, quantity: int | None = None,
    ) -> bool:
        actions = self._visit(store, plan.grid, rack, slot, item, "planned", plan.pattern, plan.rng, why,
                              quantity=quantity)
        if not actions:
            return False
        middle.extend(actions)
        plan.buys.append(actions[-1])
        plan.chosen.add(item.sku)
        plan.spend += item.price * actions[-1].quantity
        return True

    def close_plan(self, store: Store, plan: ShopperPlan, middle: list[CustomerAction]) -> ShopperPlan:
        """Frame the in-store actions (enter … pay, exit) into the planned route."""
        planned = self._frame(store, middle, bool(plan.buys), plan.rng)
        plan.planned = integrate_actions(store, planned, [], ordering=self._config.route_ordering)
        return plan

    def can_buy_more(self, plan: ShopperPlan, impulse_buys: int, price: int) -> bool:
        return (
            impulse_buys < self._config.engines.rule_based.max_impulse_items
            and len(plan.buys) + impulse_buys < plan.pattern.max_products
            and (plan.tolerance is None or plan.spend + price <= plan.budget * plan.tolerance)
        )

    async def _impulse(self, context: PerCustomerContext, plan: ShopperPlan) -> ImpulseOutcome:
        """What the shopper sees on the way. A noticed product is bought with probability
        p_buy; some further noticed products get a look without a purchase."""
        cfg = self._config
        params = cfg.engines.rule_based
        store, pattern, rng = context.store, plan.pattern, plan.rng
        out = ImpulseOutcome()
        factor = PATTERN_IMPULSE_FACTOR.get(pattern.id, 1.0)
        if factor <= 0:
            return out
        journey = build_journey(store, plan.planned, self._pathfinder, cfg.block_move_sec)
        for seen in perceive_products(store, journey, cfg.perception):
            if seen.sku in plan.chosen:
                continue
            item = next((i for i in seen.slot.items if i.sku == seen.sku), None)
            if item is None or (pattern.id == "deal_hunting" and not item.promo):
                continue
            promo = (params.promo_multiplier if item.promo else 1.0) * self._price_factor(item)
            situational = self._fx.impulse * self._demand(item_categories(seen.rack, item), plan.hour)
            p_buy = min(0.95, params.impulse_base * seen.visibility * promo * factor * situational)
            p_look = min(0.98, p_buy * (1.0 + params.browse_only_ratio))
            draw = rng.random()
            if draw < p_buy and self.can_buy_more(plan, out.buys, item.price):
                self.add_impulse_buy(store, plan, out, seen.rack, seen.slot, item, "notices it on the way")
            elif draw < p_look and out.looks < params.max_impulse_items:
                self.add_impulse_look(store, plan, out, seen.rack, seen.slot, f"glances at {item.name}")
        return out

    def add_impulse_buy(
        self, store: Store, plan: ShopperPlan, out: ImpulseOutcome,
        rack: Rack, slot: Slot, item: SlotItem, why: str,
    ) -> bool:
        actions = self._visit(store, plan.grid, rack, slot, item, "impulse", plan.pattern, plan.rng,
                              why, force_browse=True)
        if not actions:
            return False
        out.actions.extend(actions)
        out.buys += 1
        plan.chosen.add(item.sku)
        plan.spend += item.price * actions[-1].quantity
        return True

    def add_impulse_look(
        self, store: Store, plan: ShopperPlan, out: ImpulseOutcome, rack: Rack, slot: Slot, why: str,
    ) -> bool:
        tile = face_access_tile(rack, slot.face, store.grid_size, plan.grid)
        if tile is None:
            return False
        out.actions.append(CustomerAction(
            nav="path", target=tile, face=slot.face, action=Action.BROWSE,
            dwell=plan.rng.randint(2, 8), description=why, origin="impulse",
        ))
        out.looks += 1
        return True

    def _finish(self, context: PerCustomerContext, plan: ShopperPlan, impulse: ImpulseOutcome) -> EngineDecision:
        store, planned = context.store, plan.planned
        if impulse.buys and not plan.buys:  # an impulse purchase still has to be paid for
            planned = self._frame(
                store, [a for a in planned if a.action not in (Action.ENTER, Action.PAY) and a.nav != "leave"],
                True, plan.rng,
            )
        merged = integrate_actions(store, planned, impulse.actions, ordering=self._config.route_ordering)
        return EngineDecision(
            actions=merged,
            engine_type=self.engine_type,
            trace={"pattern": plan.pattern.id, "walk_out": plan.walk_out, "planned_buys": len(plan.buys),
                   "impulse_buys": impulse.buys, "impulse_looks": impulse.looks, **plan.trace, **impulse.trace},
        )

    def _pick_pattern(self, patterns: list[BehaviorPattern], rng: random.Random, basket_size: int = 0) -> BehaviorPattern:
        """Weighted draw of the trip's behavior pattern. A trip of known size draws among the
        buying patterns that hold it (or the roomiest), and its cap is raised to the size."""
        if basket_size > 0:
            buying = [p for p in patterns if p.max_products > 0] or patterns
            fits = [p for p in buying if p.max_products >= basket_size]
            patterns = fits or [max(buying, key=lambda p: p.max_products)]
        weights = [max(0.0, self._config.engines.rule_based.pattern_weights.get(p.id, 1.0)) for p in patterns]
        pattern = patterns[0] if sum(weights) <= 0 else rng.choices(patterns, weights=weights, k=1)[0]
        if basket_size > pattern.max_products:
            pattern = pattern.model_copy(update={"max_products": basket_size})
        return pattern

    def _price_factor(self, item: SlotItem) -> float:
        """(price / regular price) ** price_elasticity; 1 when the price is the regular one."""
        e = self._config.engines.rule_based.price_elasticity
        if e == 0 or item.regular_price <= 0 or item.price <= 0:
            return 1.0
        return (item.price / item.regular_price) ** e

    def _pick_item(
        self, store: Store, category: str, remaining: int, chosen: set[str], rng: random.Random,
        usual: frozenset[str] = frozenset(),
    ) -> tuple[Rack, Slot, SlotItem] | None:
        words = expand_category(category)
        attention = self._config.perception.level_attention
        promo_mult = self._config.engines.rule_based.promo_multiplier
        candidates: list[tuple[Rack, Slot, SlotItem]] = []
        weights: list[float] = []
        for rack, slot, item, rack_words, item_words in self._catalog_for(store):
            if item.sku in chosen or not (words & rack_words or words & item_words):
                continue
            fit = 1.0 if item.price <= remaining else 0.15
            candidates.append((rack, slot, item))
            weights.append(attention.get(slot.level, 0.7) * fit * (promo_mult if item.promo else 1.0)
                           * self._fx.demand_for(item_categories(rack, item)) * self._price_factor(item))
        if not candidates:
            return None
        habit = self._config.engines.rule_based.habit_prob
        if usual and habit > 0:
            mine = [i for i, c in enumerate(candidates) if c[2].name.lower() in usual]
            if mine and rng.random() < habit:
                return rng.choices([candidates[i] for i in mine], weights=[weights[i] for i in mine], k=1)[0]
        return rng.choices(candidates, weights=weights, k=1)[0]

    def _visit(
        self,
        store: Store,
        grid: list[list[bool]],
        rack: Rack,
        slot: Slot,
        item: SlotItem,
        origin: str,
        pattern: BehaviorPattern,
        rng: random.Random,
        why: str,
        *,
        force_browse: bool = False,
        quantity: int | None = None,
    ) -> list[CustomerAction]:
        """Browse (optional) + buy at the face. `quantity` None = rule draw (refills, scenario stock-up)."""
        tile = face_access_tile(rack, slot.face, store.grid_size, grid)
        if tile is None:
            return []
        if quantity is None:
            quantity = 2 if pattern.id == "routine_refill" and rng.random() < 0.4 else 1
            multi = self._config.engines.rule_based.multi_unit_prob
            if quantity == 1 and multi > 0 and rng.random() < multi:
                quantity = 2 + (1 if rng.random() < multi else 0)
            if self._fx.quantity > 1.0 and rng.random() < self._fx.quantity - 1.0:
                quantity += 1  # stocking up (typhoon, snow)
        out: list[CustomerAction] = []
        params = self._config.engines.rule_based
        looks = force_browse or pattern.browse_required_before_buy or rng.random() < params.browse_before_buy_prob
        look, pick = (rng.randint(3, 12) if looks else 0), rng.randint(2, 5)
        if looks and params.shelf_time_median_sec > 0:
            # Its own stream, seeded from the main one's current state: the main stream moves exactly
            # as with the uniform times, so baskets and model prompts stay the same.
            side = random.Random(hash(rng.getstate()))
            total = side.lognormvariate(math.log(params.shelf_time_median_sec), params.shelf_time_log_sd)
            pick = 2
            look = max(1, round(min(120.0, max(3.0, total))) - pick)
        if looks:
            out.append(CustomerAction(
                nav="path", target=tile, face=slot.face, action=Action.BROWSE,
                dwell=look, description=why, origin=origin,
            ))
        out.append(CustomerAction(
            nav="path", target=tile, face=slot.face, action=Action.BUY, dwell=pick,
            product_sku=item.sku, quantity=quantity, description=f"picks {item.name}", origin=origin,
        ))
        return out

    def _frame(
        self, store: Store, middle: list[CustomerAction], pays: bool, rng: random.Random,
    ) -> list[CustomerAction]:
        entrance: Position = entrance_position(store)
        actions = [CustomerAction(nav="path", target=entrance, action=Action.ENTER, dwell=2)]
        actions.extend(middle)
        if pays and store.counters:
            tiles = sorted(store.counters[0].service_access_tiles(store.grid_size))
            if tiles:
                actions.append(CustomerAction(nav="path", target=tiles[0], action=Action.PAY, dwell=rng.randint(15, 40)))
        actions.append(CustomerAction(nav="leave", action=Action.EXIT))
        return actions
