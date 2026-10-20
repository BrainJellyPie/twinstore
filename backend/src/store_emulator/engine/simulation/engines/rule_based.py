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

import random
import re

from store_emulator.domain.action import CustomerAction
from store_emulator.domain.behavior import BehaviorPattern
from store_emulator.domain.config import EngineType, SimulationConfig
from store_emulator.domain.engine import EngineDecision, PerCustomerContext
from store_emulator.domain.rack import Rack, Slot, SlotItem
from store_emulator.domain.store import Store
from store_emulator.domain.types import Action, PathFinder, Position, TokenUsage, stable_seed
from store_emulator.engine.routing.route_builder import (
    build_journey, entrance_position, face_access_tile, integrate_actions, perceive_products,
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

_PATTERN_IMPULSE_FACTOR: dict[str, float] = {
    "impulse_heavy": 2.5, "social_browsing": 1.6, "leisurely": 1.4, "exploratory": 1.3,
    "hungry_wandering": 1.2, "deal_hunting": 1.0, "purposeful": 0.8, "habitual": 0.6,
    "routine_refill": 0.6, "quick_snack": 0.5, "urgent": 0.25, "window_shopping": 0.0,
}

_WANDERING_PATTERNS = {"exploratory", "leisurely", "social_browsing", "hungry_wandering", "window_shopping"}


def _tokens(text: str) -> set[str]:
    out: set[str] = set()
    for raw in re.split(r"[^\w]+", text.lower()):
        if not raw or raw.isdigit():
            continue
        out.add(raw[:-1] if len(raw) > 3 and raw.endswith("s") else raw)
    return out


def _expand(category: str) -> set[str]:
    words = _tokens(category)
    expanded = set(words)
    for key, group in _SYNONYMS.items():
        if words & group or key in words:
            expanded |= group | {key}
    return expanded


class RuleBasedEngine:
    engine_type = "rule_based"

    def __init__(self, pathfinder: PathFinder, config: SimulationConfig):
        self._pathfinder = pathfinder
        self._config = config
        # Tokenized catalog per store object (one store per run; a run calls us per customer).
        self._catalog: tuple[Store, list[tuple[Rack, Slot, SlotItem, set[str], set[str]]]] | None = None

    def _catalog_for(self, store: Store) -> list[tuple[Rack, Slot, SlotItem, set[str], set[str]]]:
        if self._catalog is None or self._catalog[0] is not store:
            entries = [
                (rack, slot, item, _tokens(f"{rack.rack_name} {rack.rack_desc}"), _tokens(item.name))
                for rack in store.product_racks for slot in rack.slots for item in slot.items
            ]
            self._catalog = (store, entries)
        return self._catalog[1]

    def reset_usage(self) -> None:
        pass

    def get_usage(self) -> TokenUsage:
        return TokenUsage()

    async def decide_actions(self, context: PerCustomerContext) -> EngineDecision:
        cfg = self._config
        params = cfg.engines.rule_based
        store, persona = context.store, context.persona
        rng = random.Random(stable_seed(context.seed, "rule_based"))
        grid = store.walkable_grid()

        pattern = self._pick_pattern(context.behavior_patterns, rng)
        budget = persona.budget_max if persona.budget_max > 0 else 10**9
        tolerance = cfg.budget_tolerance or 10.0
        spend = 0
        buys: list[CustomerAction] = []
        middle: list[CustomerAction] = []
        chosen: set[str] = set()

        if pattern.id in _WANDERING_PATTERNS:
            w, h = store.grid_size
            middle.append(CustomerAction(
                nav="area", area=(1, 1, max(1, w - 2), max(1, h - 2)),
                action=Action.WANDER, dwell=rng.randint(20, 60), description="wanders the aisles",
            ))

        walk_out = pattern.allow_no_purchase and rng.random() < params.walkout_prob
        if pattern.max_products > 0 and not walk_out:
            for category in persona.preferred_categories:
                if len(buys) >= pattern.max_products:
                    break
                if rng.random() > params.planned_hit_prob:
                    continue
                pick = self._pick_item(store, category, budget - spend, chosen, rng)
                if pick is None:
                    continue
                rack, slot, item = pick
                actions = self._visit(store, grid, rack, slot, item, "planned", pattern, rng, f"looks for {category}")
                if not actions:
                    continue
                middle.extend(actions)
                buys.append(actions[-1])
                chosen.add(item.sku)
                spend += item.price * actions[-1].quantity

        planned = self._frame(store, middle, bool(buys), rng)
        planned = integrate_actions(store, planned, [], ordering=cfg.route_ordering)

        # Impulse: what the shopper sees on the way. A noticed product is bought with
        # probability p_buy; some further noticed products get a look without a purchase.
        impulse: list[CustomerAction] = []
        impulse_buys = impulse_looks = 0
        factor = _PATTERN_IMPULSE_FACTOR.get(pattern.id, 1.0)
        if factor > 0:
            journey = build_journey(store, planned, self._pathfinder, cfg.block_move_sec)
            for seen in perceive_products(store, journey, cfg.perception):
                if seen.sku in chosen:
                    continue
                item = next((i for i in seen.slot.items if i.sku == seen.sku), None)
                if item is None or (pattern.id == "deal_hunting" and not item.promo):
                    continue
                promo = params.promo_multiplier if item.promo else 1.0
                p_buy = min(0.95, params.impulse_base * seen.visibility * promo * factor)
                p_look = min(0.98, p_buy * (1.0 + params.browse_only_ratio))
                draw = rng.random()
                can_buy = (
                    impulse_buys < params.max_impulse_items
                    and len(buys) + impulse_buys < pattern.max_products
                    and spend + item.price <= budget * tolerance
                )
                if draw < p_buy and can_buy:
                    actions = self._visit(store, grid, seen.rack, seen.slot, item, "impulse", pattern, rng,
                                          "notices it on the way", force_browse=True)
                    if actions:
                        impulse.extend(actions)
                        impulse_buys += 1
                        chosen.add(item.sku)
                        spend += item.price * actions[-1].quantity
                elif draw < p_look and impulse_looks < params.max_impulse_items:
                    tile = face_access_tile(seen.rack, seen.slot.face, store.grid_size, grid)
                    if tile is not None:
                        impulse.append(CustomerAction(
                            nav="path", target=tile, face=seen.slot.face, action=Action.BROWSE,
                            dwell=rng.randint(2, 8), description=f"glances at {item.name}", origin="impulse",
                        ))
                        impulse_looks += 1

        if impulse_buys and not buys:  # an impulse purchase still has to be paid for
            planned = self._frame(store, [a for a in planned if a.action not in (Action.ENTER, Action.PAY) and a.nav != "leave"], True, rng)
        merged = integrate_actions(store, planned, impulse, ordering=cfg.route_ordering)
        return EngineDecision(
            actions=merged,
            engine_type=EngineType.RULE_BASED.value,
            trace={"pattern": pattern.id, "walk_out": walk_out, "planned_buys": len(buys),
                   "impulse_buys": impulse_buys, "impulse_looks": impulse_looks},
        )

    def _pick_pattern(self, patterns: list[BehaviorPattern], rng: random.Random) -> BehaviorPattern:
        weights = [max(0.0, self._config.engines.rule_based.pattern_weights.get(p.id, 1.0)) for p in patterns]
        if sum(weights) <= 0:
            return patterns[0]
        return rng.choices(patterns, weights=weights, k=1)[0]

    def _pick_item(
        self, store: Store, category: str, remaining: int, chosen: set[str], rng: random.Random,
    ) -> tuple[Rack, Slot, SlotItem] | None:
        words = _expand(category)
        attention = self._config.perception.level_attention
        promo_mult = self._config.engines.rule_based.promo_multiplier
        candidates: list[tuple[Rack, Slot, SlotItem]] = []
        weights: list[float] = []
        for rack, slot, item, rack_words, item_words in self._catalog_for(store):
            if item.sku in chosen or not (words & rack_words or words & item_words):
                continue
            fit = 1.0 if item.price <= remaining else 0.15
            candidates.append((rack, slot, item))
            weights.append(attention.get(slot.level, 0.7) * fit * (promo_mult if item.promo else 1.0))
        if not candidates:
            return None
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
    ) -> list[CustomerAction]:
        tile = face_access_tile(rack, slot.face, store.grid_size, grid)
        if tile is None:
            return []
        quantity = 2 if pattern.id == "routine_refill" and rng.random() < 0.4 else 1
        out: list[CustomerAction] = []
        params = self._config.engines.rule_based
        if force_browse or pattern.browse_required_before_buy or rng.random() < params.browse_before_buy_prob:
            out.append(CustomerAction(
                nav="path", target=tile, face=slot.face, action=Action.BROWSE,
                dwell=rng.randint(3, 12), description=why, origin=origin,
            ))
        out.append(CustomerAction(
            nav="path", target=tile, face=slot.face, action=Action.BUY, dwell=rng.randint(2, 5),
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
