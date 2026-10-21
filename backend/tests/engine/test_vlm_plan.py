"""VLM planning at the entrance: directory/map, item resolution, walk-outs, fallback, votes,
and no double counting of the scenario's numeric demand — with scripted fake VLMs (no server)."""

import asyncio
import io
import json
from pathlib import Path

import pytest
from PIL import Image
from pydantic import BaseModel

from store_emulator.application.presets.behavior import BEHAVIOR_PATTERNS, sample_cue
from store_emulator.domain.behavior import BehaviorCue
from store_emulator.domain.config import EngineType, SimulationConfig
from store_emulator.domain.engine import PerCustomerContext
from store_emulator.domain.persona import Persona
from store_emulator.domain.scenario import Crowding, Scenario, Weather
from store_emulator.domain.store import Store
from store_emulator.domain.types import Action, TokenUsage, Weekday
from store_emulator.engine.llm_router import EnsembleLLMClient
from store_emulator.engine.perception import (
    directory_text,
    render_store_map,
    store_directory,
)
from store_emulator.engine.routing.pathfinder import AStarPathFinder
from store_emulator.engine.simulation.engines.vlm_glance import VLMGlanceEngine
from store_emulator.engine.simulation.engines.vlm_glance.planning import match_plan_item
from store_emulator.engine.simulation.engines.vlm_glance.prompt import (
    EntryDecision,
    PlannedItem,
    combine_plan_votes,
    entry_decision_model,
)
from store_emulator.engine.simulation.simulator import PerCustomerSimulationRunner

SAMPLE = Path(__file__).resolve().parents[2] / "sample_data" / "proj_67916afd" / "runs" / "run_ab0039" / "input"

PLAN = {"enter": True, "mission": "a cold soda and something salty",
        "items": [{"category": "Drink", "product": "Pepsi 20oz", "qty": 2},
                  {"category": "Snacks", "product": "", "qty": 1},
                  {"category": "Garden", "product": "Lawn mower", "qty": 1}],
        "reason": "thirsty"}


def _store() -> Store:
    return Store.model_validate(json.loads((SAMPLE / "store.json").read_text()))


def _personas(n: int = 12) -> list[Persona]:
    return [Persona.model_validate(p) for p in json.loads((SAMPLE / "personas.json").read_text())][:n]


class _FakeVLM:
    """Answers entrance plans with a fixed plan and shelf glances with "nothing"."""

    def __init__(self, plan: dict[str, object] | None = None, *, fail: bool = False, name: str = "fake") -> None:
        self.plan = PLAN if plan is None else plan
        self.fail, self.name = fail, name
        self.plan_calls: list[dict[str, object]] = []
        self.glance_calls = 0

    def _answer[T: BaseModel](self, response_model: type[T], system: str, prompt: str, image: str | None,
                              seed: int | None, route: str | None, max_tokens: int | None) -> T:
        if issubclass(response_model, EntryDecision):
            self.plan_calls.append({"system": system, "prompt": prompt, "image": image, "seed": seed,
                                    "route": route, "max_tokens": max_tokens, "schema": response_model})
            if self.fail:
                raise TimeoutError("vlm server timed out")
            return response_model.model_validate(self.plan)  # longer item lists are trimmed by the schema
        self.glance_calls += 1
        return response_model.model_validate({"product": "", "number": 0, "interest": 0, "reason": ""})

    async def generate_structured_async[T: BaseModel](
        self, response_model: type[T], system_prompt: str, user_prompt: str,
        *, max_retries: int = 1, seed: int | None = None, route: str | None = None, max_tokens: int | None = None,
    ) -> T:
        return self._answer(response_model, system_prompt, user_prompt, None, seed, route, max_tokens)

    async def generate_structured_with_image_async[T: BaseModel](
        self, response_model: type[T], system_prompt: str, user_prompt: str, image_url: str,
        *, max_retries: int = 1, seed: int | None = None, route: str | None = None, max_tokens: int | None = None,
    ) -> T:
        assert image_url.startswith("data:image/png;base64,")
        return self._answer(response_model, system_prompt, user_prompt, image_url, seed, route, max_tokens)

    def reset_usage(self) -> None:
        pass

    def get_usage(self) -> TokenUsage:
        return TokenUsage(requests=len(self.plan_calls) + self.glance_calls)


def _config(**vlm: object) -> SimulationConfig:
    cfg = SimulationConfig(engine_type=EngineType.VLM_GLANCE)
    engine = cfg.engines.vlm_glance.model_copy(update={"max_glances": 2, "image_width": 384, **vlm})
    return cfg.model_copy(update={"engines": cfg.engines.model_copy(update={"vlm_glance": engine})})


def _context(store: Store, persona: Persona, seed: int, situation: str = "") -> PerCustomerContext:
    purposeful = next(p for p in BEHAVIOR_PATTERNS if p.id == "purposeful")
    return PerCustomerContext(
        store=store, persona=persona.model_copy(update={"budget_max": 5000}), day=Weekday.SAT, arrival_hour=14,
        concurrent_visitors_in_hour=3, cue=BehaviorCue(state="목마름"), behavior_patterns=[purposeful],
        seed=seed, situation=situation,
    )


def _buys(decision_actions: list[object]) -> list[tuple[str, int]]:
    return [(a.product_sku, a.quantity) for a in decision_actions if getattr(a, "action", None) == Action.BUY]  # type: ignore[attr-defined]


@pytest.mark.parametrize("tolerance,price,expected", [
    (None, 60000, True), (0.0, 100, False), (0.0, 0, True), (1.5, 7500, True), (1.5, 7501, False),
])
def test_impulse_limit_honors_disabled_and_zero_caps(tolerance, price, expected):
    from store_emulator.engine.simulation.engines.rule_based import RuleBasedEngine

    config = SimulationConfig(budget_tolerance=tolerance)
    engine = RuleBasedEngine(AStarPathFinder(), config)
    plan, _ = engine._begin_plan(_context(_store(), _personas()[0], seed=0))
    assert engine.can_buy_more(plan, 0, price) is expected
    assert not engine.can_buy_more(plan, config.engines.rule_based.max_impulse_items, 0)


@pytest.mark.parametrize("tolerance,price,quantity,expected", [
    (None, 60000, 2, 2), (0.0, 100, 1, 0), (0.0, 0, 2, 2), (1.5, 2500, 4, 3), (1.5, 7501, 1, 0),
])
def test_vlm_planned_quantity_honors_disabled_and_zero_caps(tolerance, price, quantity, expected):
    store = _store()
    for rack in store.product_racks:
        for slot in rack.slots:
            for item in slot.items:
                if item.name == "Pepsi 20oz":
                    item.price = price
    fake = _FakeVLM({"enter": True, "mission": "Buy Pepsi", "items": [
        {"category": "Drink", "product": "Pepsi 20oz", "qty": quantity},
    ], "reason": "needed"})
    engine = VLMGlanceEngine(llm=fake, pathfinder=AStarPathFinder(),
                            config=_config().model_copy(update={"budget_tolerance": tolerance}))
    engine.prepare(store)
    plan = asyncio.run(engine._vlm_plan(_context(store, _personas()[0], seed=0)))
    assert sum(b.quantity for b in plan.buys) == expected


def test_disabled_cap_does_not_put_a_synthetic_budget_in_glance_prompts(monkeypatch):
    from store_emulator.engine.simulation.engines.vlm_glance import engine as vlm_module

    limits = []
    original = vlm_module.user_prompt

    def capture(*args, **kwargs):
        limits.append(kwargs["money_left"])
        return original(*args, **kwargs)

    monkeypatch.setattr(vlm_module, "user_prompt", capture)
    store = _store()
    config = _config(glance_policy="all").model_copy(update={"budget_tolerance": None})
    engine = VLMGlanceEngine(llm=_FakeVLM(), pathfinder=AStarPathFinder(), config=config)
    engine.prepare(store)
    asyncio.run(engine.decide_actions(_context(store, _personas()[0], seed=11)))
    assert limits
    assert all(limit is None for limit in limits)


def test_a_free_planned_item_is_kept_after_the_budget_is_fully_spent():
    store = _store()
    names = list(dict.fromkeys(item.name for rack in store.product_racks for slot in rack.slots for item in slot.items))[:2]
    for rack in store.product_racks:
        for slot in rack.slots:
            for item in slot.items:
                if item.name in names:
                    item.price = 7500 if item.name == names[0] else 0
    fake = _FakeVLM({"enter": True, "mission": "Buy two products", "items": [
        {"product": name, "qty": 1} for name in names
    ], "reason": "needed"})
    engine = VLMGlanceEngine(llm=fake, pathfinder=AStarPathFinder(), config=_config())
    engine.prepare(store)
    plan = asyncio.run(engine._vlm_plan(_context(store, _personas()[0], seed=0)))
    assert len(plan.buys) == 2
    assert plan.spend == 7500


@pytest.mark.parametrize("value", [-0.01, "NaN", "Infinity", "-Infinity"])
def test_invalid_budget_tolerance_is_rejected(value):
    from pydantic import ValidationError

    with pytest.raises(ValidationError):
        SimulationConfig.model_validate({"budget_tolerance": value})


def test_directory_and_map_describe_the_store():
    store = _store()
    directory = store_directory(store)
    labels = [d.label for d in directory]
    assert labels[:2] == ["Drink", "Frozen food"] and "Snacks" in labels and "Ice cream" in labels
    drink = directory[0]
    assert len(drink.examples) == 3 and drink.min_price <= drink.max_price and len(drink.rack_ids) == 3
    text = directory_text(directory, "USD")
    assert text.startswith("- Drink: ") and "$" in text
    a, b = render_store_map(store, width=512), render_store_map(store, width=512)
    assert a.png == b.png and a.size[0] == 512
    # A promoted item puts a red SALE ribbon on its rack.
    rack = store.product_racks[0]
    promo_item = rack.slots[0].items[0].model_copy(update={"promo": "1+1"})
    slot = rack.slots[0].model_copy(update={"items": [promo_item, *rack.slots[0].items[1:]]})
    promoted = store.model_copy(update={"racks": [rack.model_copy(update={"slots": [slot, *rack.slots[1:]]}),
                                                  *store.racks[1:]]})
    reds = sum(1 for px in Image.open(io.BytesIO(render_store_map(promoted).png)).convert("RGB").get_flattened_data()
               if px == (214, 32, 39))
    assert reds > sum(1 for px in Image.open(io.BytesIO(a.png)).convert("RGB").get_flattened_data() if px == (214, 32, 39))
    assert "on sale: " in directory_text(store_directory(promoted), "USD")


def test_plan_items_resolve_by_name_words_category_and_demand_category():
    store = _store()
    engine = VLMGlanceEngine(llm=_FakeVLM(), pathfinder=AStarPathFinder(), config=_config())  # type: ignore[arg-type]
    catalog = engine._catalog_for(store)  # pyright: ignore[reportPrivateUsage]
    exact = match_plan_item(PlannedItem(category="Drink", product="pepsi 20oz"), catalog)
    assert exact.how == "exact" and {e[2].name for e in exact.candidates} == {"Pepsi 20oz"}
    fuzzy = match_plan_item(PlannedItem(category="Drink", product="Pepsi"), catalog)
    assert fuzzy.how == "name" and all("Pepsi" in e[2].name for e in fuzzy.candidates)
    words = match_plan_item(PlannedItem(category="", product="some ramen"), catalog)
    assert words.how == "words" and all("Ramen" in e[2].name for e in words.candidates)
    category = match_plan_item(PlannedItem(category="Snacks", product="something"), catalog)
    assert category.how == "category" and {e[0].rack_name for e in category.candidates} == {"Snacks 1", "Snacks 2"}
    assert match_plan_item(PlannedItem(category="Ice cream", product="popsicle"), catalog).how == "name"
    demand = match_plan_item(PlannedItem(category="gelato"), catalog)  # no sign says gelato; ice cream does
    assert demand.how == "demand_category" and {e[0].rack_name for e in demand.candidates} >= {"Ice cream 1"}
    assert match_plan_item(PlannedItem(category="Garden", product="Lawn mower"), catalog).how == "unresolved"
    assert exact.key == match_plan_item(PlannedItem(product="PEPSI 20OZ"), catalog).key


def test_vlm_plan_becomes_planned_purchases_with_the_named_quantities():
    store = _store()
    vlm = _FakeVLM()
    engine = VLMGlanceEngine(llm=vlm, pathfinder=AStarPathFinder(), config=_config())  # type: ignore[arg-type]
    decision = asyncio.run(engine.decide_actions(_context(store, _personas()[0], seed=11, situation="a heatwave")))
    actions = [a.action for a in decision.actions]
    assert actions[0] == Action.ENTER and actions[-1] == Action.EXIT and Action.PAY in actions
    names = {i.sku: i.name for r in store.product_racks for s in r.slots for i in s.items}
    buys = _buys(decision.actions)
    assert (next(sku for sku, n in names.items() if n == "Pepsi 20oz"), 2) in buys and len(buys) == 2
    assert all(a.origin == "planned" for a in decision.actions if a.action == Action.BUY)
    call = vlm.plan_calls[0]
    # max(plan_max_tokens, 200 + 70 per allowed item): a 3-item plan gets 410 tokens.
    assert call["image"] is not None and call["route"] == _personas()[0].id and call["max_tokens"] == 410
    assert "Today: a heatwave." in str(call["prompt"]) and "- Drink: " in str(call["prompt"])
    assert decision.trace["plan_source"] == "vlm" and decision.trace["mission"] == PLAN["mission"]
    meta = engine.metadata()
    planning = meta["planning"]
    assert isinstance(planning, dict)
    assert planning["enter_rate"] == 1.0 and planning["mean_items_named"] == 3
    assert planning["resolved_by"] == {"exact": 1, "category": 1, "unresolved": 1}
    assert planning["resolution_rate"] == pytest.approx(2 / 3, abs=1e-3)
    assert sorted(c for c, _ in planning["top_categories"]) == ["Drink", "Snacks"]  # type: ignore[union-attr]
    record = meta["plan_records"][0]  # type: ignore[index]
    assert record["resolved"][2][2] == "unresolved"  # type: ignore[index]


def test_same_customer_gets_the_same_plan_and_text_only_mode_skips_the_image():
    store, persona = _store(), _personas()[3]
    runs = []
    for _ in range(2):
        engine = VLMGlanceEngine(llm=_FakeVLM(), pathfinder=AStarPathFinder(), config=_config())  # type: ignore[arg-type]
        runs.append(_buys(asyncio.run(engine.decide_actions(_context(store, persona, seed=5))).actions))
    assert runs[0] == runs[1]
    vlm = _FakeVLM()
    engine = VLMGlanceEngine(llm=vlm, pathfinder=AStarPathFinder(), config=_config(entrance_image=False, max_plan_items=1))  # type: ignore[arg-type]
    decision = asyncio.run(engine.decide_actions(_context(store, persona, seed=5)))
    assert vlm.plan_calls[0]["image"] is None
    assert vlm.plan_calls[0]["schema"] is entry_decision_model(1)
    assert len(_buys(decision.actions)) == 1  # max_plan_items caps the plan (schema-trimmed)
    assert len(engine.metadata()["plan_records"][0]["items"]) == 1  # type: ignore[index]


def test_enter_false_walks_out_without_buying_or_looking():
    store = _store()
    vlm = _FakeVLM({"enter": False, "mission": "too crowded", "items": [], "reason": "queue"})
    config = _config(glance_policy="all")
    pf = AStarPathFinder()
    engine = VLMGlanceEngine(llm=vlm, pathfinder=pf, config=config)  # type: ignore[arg-type]
    runner = PerCustomerSimulationRunner(config, engine, pf, sample_cue, BEHAVIOR_PATTERNS)
    aggregated, results = asyncio.run(runner.run(store.model_copy(deep=True), _personas(6), max_concurrent=3))
    assert len(results) == 6 and aggregated.summary.total_customers == 6
    assert aggregated.summary.buyers == 0 and aggregated.summary.conversion_rate == 0.0
    assert all(r.total_spent == 0 and r.timeline[0].action == Action.ENTER for r in results)
    assert vlm.glance_calls == 0
    planning = engine.metadata()["planning"]
    assert isinstance(planning, dict) and planning["enter_rate"] == 0.0


def test_failed_plan_falls_back_to_the_rule_plan_and_is_counted():
    store, personas = _store(), _personas(5)
    failing = VLMGlanceEngine(llm=_FakeVLM(fail=True), pathfinder=AStarPathFinder(), config=_config())  # type: ignore[arg-type]
    rule = VLMGlanceEngine(llm=_FakeVLM(), pathfinder=AStarPathFinder(), config=_config(plan_policy="rule"))  # type: ignore[arg-type]
    for i, persona in enumerate(personas):
        a = asyncio.run(failing.decide_actions(_context(store, persona, seed=100 + i)))
        b = asyncio.run(rule.decide_actions(_context(store, persona, seed=100 + i)))
        assert _buys(a.actions) == _buys(b.actions)
        assert a.trace["plan_source"] == "fallback" and "TimeoutError" in str(a.trace["plan_error"])
    planning = failing.metadata()["planning"]
    assert isinstance(planning, dict) and planning["plan_errors"] == 5 and planning["enter_rate"] is None
    assert rule.metadata()["planning"] is None and rule.metadata()["plan_records"] == []


def _baskets(scenario: Scenario | None, policy: str) -> list[list[tuple[str, int]]]:
    """Planned baskets of a fixed panel, with the store left untouched by the scenario."""
    store = _store()
    config = _config(plan_policy=policy).model_copy(update={"scenario": scenario})
    engine = VLMGlanceEngine(llm=_FakeVLM(), pathfinder=AStarPathFinder(), config=config)  # type: ignore[arg-type]
    out: list[list[tuple[str, int]]] = []
    for i, persona in enumerate(_personas(40)):
        context = PerCustomerContext(
            store=store, persona=persona, day=Weekday.SAT, arrival_hour=persona.arrival_hour,
            concurrent_visitors_in_hour=3, cue=BehaviorCue(), behavior_patterns=BEHAVIOR_PATTERNS, seed=500 + i,
        )
        decision = asyncio.run(engine.decide_actions(context))
        out.append([(a.product_sku, a.quantity) for a in decision.actions
                    if a.action == Action.BUY and a.origin == "planned"])
    return out


def test_vlm_plans_ignore_the_scenarios_numeric_demand_and_walkout_multipliers():
    # Typhoon: hot food ×1.8, water ×1.7, stock-up quantities ×1.6; packed store: walk-outs ×2.5.
    storm = Scenario(id="storm", weather=Weather.TYPHOON, crowding=Crowding.PACKED)
    assert _baskets(storm, "vlm") == _baskets(None, "vlm")
    # The rule planner does apply them, so the same scenario changes its baskets.
    assert _baskets(storm, "rule") != _baskets(None, "rule")


def test_plan_votes_majority_enter_and_items_named_by_half():
    def key(item: PlannedItem) -> str:
        return (item.product or item.category).lower()

    a = EntryDecision(enter=True, mission="soda run", items=[PlannedItem(category="Drink", product="Pepsi", qty=2),
                                                             PlannedItem(category="Snacks", product="Takis")])
    b = EntryDecision(enter=True, mission="drinks", items=[PlannedItem(category="Drink", product="pepsi", qty=3)])
    c = EntryDecision(enter=False, mission="nope")
    d = EntryDecision(enter=True, items=[PlannedItem(category="Snacks", product="takis"),
                                         PlannedItem(category="Ice cream", product="Magnum")])
    plan, agreement = combine_plan_votes([("a", a), ("b", b), ("c", c), ("d", d)], key)
    assert plan.enter and agreement == 0.75
    assert [(i.product, i.qty) for i in plan.items] == [("Pepsi", 2), ("Takis", 1)]
    assert plan.mission == "soda run"
    out, agreement = combine_plan_votes([("a", a), ("c", c), ("c2", c)], key)
    assert not out.enter and out.items == [] and agreement == pytest.approx(2 / 3)


def test_vote_ensemble_plans_with_every_member():
    store = _store()
    yes = _FakeVLM()
    also = _FakeVLM({**PLAN, "items": [{"category": "Drink", "product": "Pepsi 20oz", "qty": 1}]})
    no = _FakeVLM({"enter": False, "mission": "", "items": [], "reason": ""})
    ens = EnsembleLLMClient([("a", 1.0, yes), ("b", 1.0, also), ("c", 1.0, no)], mode="vote")  # type: ignore[list-item]
    engine = VLMGlanceEngine(llm=ens, pathfinder=AStarPathFinder(), config=_config())
    decision = asyncio.run(engine.decide_actions(_context(store, _personas()[0], seed=3)))
    assert len(yes.plan_calls) == len(also.plan_calls) == len(no.plan_calls) == 1
    names = {i.sku: i.name for r in store.product_racks for s in r.slots for i in s.items}
    assert [names[sku] for sku, _ in _buys(decision.actions)] == ["Pepsi 20oz"]  # only Pepsi had a majority
    record = engine.metadata()["plan_records"][0]  # type: ignore[index]
    assert record["source"] == "vote" and record["agreement"] == pytest.approx(2 / 3)  # type: ignore[index]


def test_run_options_and_cli_switch_the_plan_policy():
    from store_emulator.application.simulation import RunOptions, apply_options
    from store_emulator.cli import main

    assert SimulationConfig().engines.vlm_glance.plan_policy == "vlm"
    cfg = apply_options(SimulationConfig(), RunOptions(engine_type=EngineType.VLM_GLANCE, plan_policy="rule"))
    assert cfg.engines.vlm_glance.plan_policy == "rule"
    assert apply_options(SimulationConfig(), RunOptions()).engines.vlm_glance.plan_policy == "vlm"
    with pytest.raises(SystemExit):
        main(["simulate", "--plan-policy", "maybe", "--out", "x"])


class _CutOffOnceVLM(_FakeVLM):
    """The first plan answer runs out of tokens, as long supermarket lists did."""

    def _answer[T: BaseModel](self, response_model: type[T], system: str, prompt: str, image: str | None,
                              seed: int | None, route: str | None, max_tokens: int | None) -> T:
        if issubclass(response_model, EntryDecision) and not self.plan_calls:
            self.plan_calls.append({"max_tokens": max_tokens})
            raise RuntimeError("The output is incomplete due to a max_tokens length limit.")
        return super()._answer(response_model, system, prompt, image, seed, route, max_tokens)


def test_cut_off_plan_is_retried_with_twice_the_budget():
    store = _store()
    vlm = _CutOffOnceVLM()
    engine = VLMGlanceEngine(llm=vlm, pathfinder=AStarPathFinder(), config=_config())  # type: ignore[arg-type]
    decision = asyncio.run(engine.decide_actions(_context(store, _personas()[0], seed=11, situation="")))
    assert [c["max_tokens"] for c in vlm.plan_calls] == [410, 820]
    assert decision.trace["plan_source"] == "vlm"


def test_trip_breadth_keeps_the_first_planned_categories_and_fills_within_them():
    store = _store()
    plan = {"enter": True, "mission": "stock up", "reason": "weekly",
            "items": [{"category": "Drink", "product": "Pepsi 20oz", "qty": 1},
                      {"category": "Snacks", "product": "", "qty": 1},
                      {"category": "Ice cream", "product": "", "qty": 1},
                      {"category": "Frozen food", "product": "", "qty": 1}]}
    engine = VLMGlanceEngine(llm=_FakeVLM(plan), pathfinder=AStarPathFinder(), config=_config())  # type: ignore[arg-type]
    persona = _personas()[0].model_copy(update={"basket_size": 4, "basket_kinds": 2})
    decision = asyncio.run(engine.decide_actions(_context(store, persona, seed=3)))
    rack_of = {i.sku: r.rack_name.rsplit(" ", 1)[0] for r in store.product_racks for s in r.slots for i in s.items}
    buys = _buys(decision.actions)
    assert len({sku for sku, _ in buys}) == 4
    assert {rack_of[sku] for sku, _ in buys} == {"Drink", "Snacks"}       # the model's first two categories
    record = engine.metadata()["plan_records"][0]  # type: ignore[index]
    hows = [r[2] for r in record["resolved"]]  # type: ignore[index]
    assert hows.count("breadth") == 2 and hows.count("breadth_fill") == 2


def test_needs_are_a_seeded_draw_at_each_category_rate():
    from store_emulator.engine.simulation.engines.vlm_glance.prompt import (
        plan_user_prompt,
    )

    store = _store()
    persona = _personas()[0].model_copy(update={"category_rates": {"Drink": 0.9, "Snacks": 0.5, "Ice cream": 0.1}})
    engine = VLMGlanceEngine(llm=_FakeVLM(), pathfinder=AStarPathFinder(), config=_config())  # type: ignore[arg-type]
    draws = [engine._needs(_context(store, persona, seed=s)) for s in range(400)]  # pyright: ignore[reportPrivateUsage]
    assert all(d is not None for d in draws)
    share = {c: sum(c in d[0] for d in draws if d) / len(draws) for c in ("Drink", "Snacks", "Ice cream")}
    assert abs(share["Drink"] - 0.9) < 0.05 and abs(share["Snacks"] - 0.5) < 0.07 and abs(share["Ice cream"] - 0.1) < 0.05
    assert draws[3] == engine._needs(_context(store, persona, seed=3))  # pyright: ignore[reportPrivateUsage]
    assert engine._needs(_context(store, _personas()[0], seed=1)) is None  # pyright: ignore[reportPrivateUsage]
    text = plan_user_prompt(persona, BehaviorCue(state=""), BEHAVIOR_PATTERNS[0], day=Weekday.MON, hour=9, situation="",
                            budget=None, currency="USD", directory="", needs=(["Drink"], ["Snacks", "Ice cream"]))
    assert "needed this trip: Drink." in text and "Still stocked at home (bought recently): Snacks, Ice cream." in text


def test_a_situation_scales_the_need_draw_by_its_measured_ratio():
    from store_emulator.domain.scenario import Scenario, ScenarioPriors, Season

    store = _store()
    persona = _personas()[0].model_copy(update={"category_rates": {"Drink": 0.3, "Snacks": 0.3}})
    priors = ScenarioPriors(need_ratio={"season:summer": {"cold_drinks": 2.0, "snacks": 0.5}})
    summer = _config().model_copy(update={"scenario": Scenario(season=Season.SUMMER), "scenario_priors": priors})
    engine = VLMGlanceEngine(llm=_FakeVLM(), pathfinder=AStarPathFinder(), config=summer)  # type: ignore[arg-type]
    engine.prepare(store)
    draws = [engine._needs(_context(store, persona, seed=s)) for s in range(600)]  # pyright: ignore[reportPrivateUsage]
    drink = sum("Drink" in d[0] for d in draws if d) / len(draws)
    snacks = sum("Snacks" in d[0] for d in draws if d) / len(draws)
    assert abs(drink - 0.6) < 0.06 and abs(snacks - 0.15) < 0.05


@pytest.mark.parametrize("period", ["day:weekday", "hour:evening"])
def test_zero_need_ratio_keeps_overlapping_categories_out_of_the_need_draw(period):
    from store_emulator.domain.scenario import ScenarioPriors

    store = _store()
    persona = _personas()[0].model_copy(update={"category_rates": {"Water": 1.0}, "usual_products": []})
    priors = ScenarioPriors(need_ratio={period: {"water": 0.0, "cold_drinks": 2.0}})
    config = _config().model_copy(update={"scenario": Scenario(), "scenario_priors": priors})
    fake = _FakeVLM()
    engine = VLMGlanceEngine(llm=fake, pathfinder=AStarPathFinder(), config=config)
    engine.prepare(store)
    draws = [engine._needs(_context(store, persona, seed=s).model_copy(update={"arrival_hour": 19}))
             for s in range(100)]
    assert all(draw == ([], ["Water"]) for draw in draws)
    assert fake.plan_calls == [] and fake.glance_calls == 0


def test_a_needed_category_names_the_households_usual_products_there():
    store = _store()
    rack = next(r for r in store.product_racks if r.rack_name and any(s.items for s in r.slots))
    items = [i.name for s in rack.slots for i in s.items][:3]
    persona = _personas()[0].model_copy(update={"category_rates": {rack.rack_name: 1.0, "Nothing here": 1.0},
                                                "usual_products": ["Not on the shelf", *items]})
    engine = VLMGlanceEngine(llm=_FakeVLM(), pathfinder=AStarPathFinder(), config=_config())  # type: ignore[arg-type]
    needs = engine._needs(_context(store, persona, seed=1))  # pyright: ignore[reportPrivateUsage]
    assert needs is not None
    named = next(n for n in needs[0] if n.startswith(rack.rack_name))
    assert named == f"{rack.rack_name} (they usually take {items[0]} or {items[1]})"
    assert "Nothing here" in needs[0]                       # no usual product there: the bare category


@pytest.mark.parametrize("reverse_racks", [False, True])
def test_usual_product_is_named_for_every_needed_category_that_stocks_it(reverse_racks):
    store = _store()
    source = next(r for r in store.product_racks if r.rack_name and any(s.items for s in r.slots))
    target = next(r for r in store.product_racks if r.rack_name and r.rack_name != source.rack_name and r.slots)
    item = next(i for s in source.slots for i in s.items)
    target.slots[0].items = [item.model_copy(deep=True)]
    if reverse_racks:
        store.racks.reverse()
    persona = _personas()[0].model_copy(update={
        "category_rates": {source.rack_name: 1.0, target.rack_name: 1.0}, "usual_products": [item.name],
    })
    engine = VLMGlanceEngine(llm=_FakeVLM(), pathfinder=AStarPathFinder(), config=_config())
    needs = engine._needs(_context(store, persona, seed=1))
    assert needs is not None
    assert f"{source.rack_name} (they usually take {item.name})" in needs[0]
    assert f"{target.rack_name} (they usually take {item.name})" in needs[0]


def test_a_needed_category_keeps_its_place_under_the_breadth_limit():
    store = _store()
    plan = {"enter": True, "mission": "stock up", "reason": "weekly",
            "items": [{"category": "Drink", "product": "Pepsi 20oz", "qty": 1},
                      {"category": "Snacks", "product": "", "qty": 1},
                      {"category": "Ice cream", "product": "", "qty": 1},
                      {"category": "Frozen food", "product": "", "qty": 1}]}
    engine = VLMGlanceEngine(llm=_FakeVLM(plan), pathfinder=AStarPathFinder(), config=_config())  # type: ignore[arg-type]
    persona = _personas()[0].model_copy(update={"basket_size": 4, "basket_kinds": 2, "category_rates": {"Ice cream": 1.0}})
    decision = asyncio.run(engine.decide_actions(_context(store, persona, seed=3)))
    rack_of = {i.sku: r.rack_name.rsplit(" ", 1)[0] for r in store.product_racks for s in r.slots for i in s.items}
    # ran out of ice cream: it stays in the trip; the model's first other category fills the second place
    assert {rack_of[sku] for sku, _ in _buys(decision.actions)} == {"Ice cream", "Drink"}


@pytest.mark.parametrize("cause", ["promotion", "attention"])
def test_zero_weight_plan_items_are_skipped_without_failing_or_claiming_duplicates(cause):
    store = _store()
    config = _config()
    if cause == "promotion":
        config.engines.rule_based.promo_multiplier = 0
        for rack in store.product_racks:
            for slot in rack.slots:
                for item in slot.items:
                    item.promo = "Special offer"
    else:
        config.perception.level_attention = {1: 0, 2: 0, 3: 0, 4: 0}
    engine = VLMGlanceEngine(llm=_FakeVLM(), pathfinder=AStarPathFinder(), config=config)
    plan = asyncio.run(engine._vlm_plan(_context(store, _personas()[0], seed=0)))
    assert plan.entered and not plan.buys
    assert [entry[2] for entry in engine.plan_log[-1].resolved] == ["unavailable", "unavailable", "unresolved"]
