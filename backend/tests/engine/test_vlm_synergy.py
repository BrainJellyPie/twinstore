"""VLM synergy of a neighboring venue: counterfactual trip contexts and the paired basket effect,
with a scripted fake VLM (no server)."""

import asyncio
import json
from pathlib import Path

import pytest
from pydantic import BaseModel

from store_emulator.application.presets.behavior import BEHAVIOR_PATTERNS, sample_cue
from store_emulator.domain.config import EngineType, SimulationConfig
from store_emulator.domain.persona import Persona
from store_emulator.domain.scenario import Scenario, Weather
from store_emulator.domain.store import DaySchedule, Store
from store_emulator.domain.town import Town, TownArrival, TownSpec, VenueCategory
from store_emulator.domain.types import TokenUsage, Weekday
from store_emulator.engine.routing.pathfinder import AStarPathFinder
from store_emulator.engine.scenario import compile_scenario, priors_for
from store_emulator.engine.simulation.engines.vlm_glance import VLMGlanceEngine
from store_emulator.engine.simulation.engines.vlm_glance.prompt import EntryDecision
from store_emulator.engine.town import (
    counterfactual_arrival,
    estimate_demand,
    generate_town,
    place_venue,
    synergy_analysis,
    town_context_text,
)
from store_emulator.engine.town.vlm_synergy import vlm_basket_synergy
from tests.engine.test_reproducibility import _RecordingEngine

SAMPLE = Path(__file__).resolve().parents[2] / "sample_data" / "proj_67916afd" / "runs" / "run_ab0039" / "input"


@pytest.mark.parametrize("opening", [0, 9, 23])
@pytest.mark.parametrize("is_open", [False, True])
def test_synergy_flow_panels_and_progress_use_the_store_open_window(town, opening, is_open):
    store = Store.model_validate(json.loads((SAMPLE / "store.json").read_text()))
    store.weekly_schedule = [DaySchedule(day=Weekday.WED, is_open=is_open, open_hour=opening, close_hour=opening + 1)]
    pool = [Persona.model_validate(p) for p in json.loads((SAMPLE / "personas.json").read_text())][:300]
    # Explicitly model the store's window: the default neighborhood window starts at 07:00
    # and cannot be used as the oracle for a store open at midnight.
    baseline = estimate_demand(town, hours=[opening] if is_open else [])
    before = town.model_dump()
    engine = _RecordingEngine()
    progress = []
    result = asyncio.run(vlm_basket_synergy(
        town, "cafe-next-door", store, pool, config=SimulationConfig(seed=5), engine=engine,
        pathfinder=AStarPathFinder(), cue_sampler=sample_cue, patterns=BEHAVIOR_PATTERNS,
        customers=12, model_label="fake", on_progress=lambda *args: progress.append(args),
    ))
    assert result.visitors_with == pytest.approx(baseline.hourly_totals[opening] if is_open else 0, abs=0.01)
    assert result.panel_customers == len(engine.contexts)
    assert all(context.day == Weekday.WED and context.arrival_hour == opening for context in engine.contexts.values())
    total = result.panel_customers + result.affected_customers
    assert progress[-1][1:] == (total, total)
    if not is_open:
        assert not engine.contexts and result.visitors_without == result.delta_revenue_per_day == 0
    if result.affected_comparison is not None:
        assert result.affected_comparison.paired_customers == result.affected_customers
    assert town.model_dump() == before


class CafeLoverVLM:
    """Visitors who came from the café plan two drinks; everyone else one snack."""

    def __init__(self) -> None:
        self.calls = 0
        self.run_calls = 0

    def _answer[T: BaseModel](self, response_model: type[T], prompt: str) -> T:
        self.calls += 1
        self.run_calls += 1
        if issubclass(response_model, EntryDecision):
            if "Came straight from the cafe" in prompt:
                item = {"category": "Drink", "product": "Pepsi 20oz", "qty": 2}
            else:
                item = {"category": "Snacks", "product": "", "qty": 1}
            return response_model.model_validate({"mission": "errand", "enter": True, "items": [item]})
        return response_model.model_validate({"product": "", "number": 0, "interest": 0})

    async def generate_structured_async[T: BaseModel](
        self, response_model: type[T], system_prompt: str, user_prompt: str,
        *, max_retries: int = 1, seed: int | None = None, route: str | None = None, max_tokens: int | None = None,
    ) -> T:
        return self._answer(response_model, user_prompt)

    async def generate_structured_with_image_async[T: BaseModel](
        self, response_model: type[T], system_prompt: str, user_prompt: str, image_url: str,
        *, max_retries: int = 1, seed: int | None = None, route: str | None = None, max_tokens: int | None = None,
    ) -> T:
        return self._answer(response_model, user_prompt)

    def reset_usage(self) -> None:
        self.run_calls = 0

    def get_usage(self) -> TokenUsage:
        return TokenUsage(requests=self.run_calls)


@pytest.fixture(scope="module")
def town() -> Town:
    base = generate_town(TownSpec(seed=4, size_m=400, n_competitors=1, venue_density=0.0))
    focal = base.get_venue(base.focal_venue_id)
    assert focal is not None
    return place_venue(base, VenueCategory.CAFE, focal.x + 12, focal.y, venue_id="cafe-next-door", name="Corner Cafe")


def test_counterfactual_arrival_reroutes_only_visitors_from_the_removed_venue(town: Town):
    without = town.model_copy(update={"venues": [v for v in town.venues if v.id != "cafe-next-door"]})
    demand_without = estimate_demand(without)
    linked = TownArrival(
        persona_id="x~t0", source_persona_id="x", hour=9, segment="linked", age_group="30s", purpose="after cafe visit",
        origin_kind="cafe", origin_name="Corner Cafe", distance_m=12.0, walk_min=0.2, came_from_venue="cafe",
        came_from_venue_id="cafe-next-door", is_linked_trip=True,
    )
    moved = counterfactual_arrival(linked, "cafe-next-door", demand_without, seed=1)
    assert not moved.is_linked_trip and moved.segment != "linked" and moved.origin_building_id
    assert without.get_building(moved.origin_building_id) is not None
    assert moved == counterfactual_arrival(linked, "cafe-next-door", demand_without, seed=1)
    assert "cafe" not in town_context_text(moved, without).lower()
    assert counterfactual_arrival(linked, "some-other-venue", demand_without, seed=1) is linked


def test_vlm_basket_synergy_pairs_the_same_visitors_with_and_without_the_venue(town: Town):
    store = Store.model_validate(json.loads((SAMPLE / "store.json").read_text()))
    pool = [Persona.model_validate(p) for p in json.loads((SAMPLE / "personas.json").read_text())][:300]
    config = SimulationConfig(engine_type=EngineType.VLM_GLANCE, seed=5)
    pf = AStarPathFinder()
    llm = CafeLoverVLM()
    phases: list[tuple[str, int, int]] = []
    result = asyncio.run(vlm_basket_synergy(
        town, "cafe-next-door", store, pool, config=config,
        engine=VLMGlanceEngine(llm=llm, pathfinder=pf, config=config), pathfinder=pf, cue_sampler=sample_cue,
        patterns=BEHAVIOR_PATTERNS, customers=12, model_label="fake", on_progress=lambda *a: phases.append(a),
    ))
    assert result.delta_visitors > 0 and result.linked_visitors_from_venue > 0
    assert result.visitors_with - result.visitors_without == pytest.approx(result.delta_visitors, abs=1e-2)
    assert result.panel_customers == 12 and 0 < result.affected_customers <= 8
    assert 0 < result.affected_share < 1
    # Café visitors plan two Pepsis instead of a snack: spend up, Drink up, Snacks down.
    assert result.delta_spend_per_visitor > 0 and result.delta_spend_ci_low is not None
    assert result.prob_spend_higher is not None and result.prob_spend_higher > 0.5
    shifts = {c.category: c for c in result.category_shifts}
    assert shifts["Drink"].spend_diff > 0 and shifts["Snacks"].spend_diff < 0
    expected = (result.delta_revenue_from_visitors + result.delta_revenue_from_baskets)
    assert result.delta_revenue_per_day == pytest.approx(expected, abs=0.05)
    assert result.revenue_per_day_with - result.revenue_per_day_without == pytest.approx(
        result.delta_revenue_per_day, abs=0.05)
    assert result.examples and all(e.context_with != e.context_without for e in result.examples)
    assert any("cafe" in e.context_with.lower() for e in result.examples)
    assert result.affected_comparison is not None
    assert result.affected_comparison.paired_customers == result.affected_customers
    # Unaffected visitors are simulated once: 12 with the venue + the affected ones again.
    assert phases[-1][1] == phases[-1][2] == 12 + result.affected_customers
    assert result.vlm_requests == llm.calls and result.plan_errors == 0


@pytest.mark.parametrize("store_type", ["Convenience store", "supermarket"])
def test_synergy_uses_the_store_formats_scenario_effects_and_the_synergy_tables_distance(town: Town, store_type: str):
    store = Store.model_validate(json.loads((SAMPLE / "store.json").read_text()))
    store.type = store_type
    pool = [Persona.model_validate(p) for p in json.loads((SAMPLE / "personas.json").read_text())][:300]
    rain = Scenario(id="rain", name="Rain", weather=Weather.RAIN)
    traffic = compile_scenario(rain, priors_for(store_type)).base_traffic
    assert compile_scenario(rain, priors_for("supermarket")).base_traffic != compile_scenario(rain).base_traffic
    result = asyncio.run(vlm_basket_synergy(
        town, "cafe-next-door", store, pool, config=SimulationConfig(seed=5, scenario=rain), engine=_RecordingEngine(),
        pathfinder=AStarPathFinder(), cue_sampler=sample_cue, patterns=BEHAVIOR_PATTERNS, customers=4,
    ))
    # The sample layout opens 8–20 on a weekday.
    expected = estimate_demand(town, hours=range(8, 20), traffic_multiplier=traffic).total_daily_visitors
    assert result.visitors_with == pytest.approx(expected, abs=0.01)
    row = next(r for r in synergy_analysis(town) if r.venue_id == "cafe-next-door")
    assert result.distance_m == row.distance_m  # walking distance, as in the synergy table


@pytest.mark.parametrize("currency", ["USD", "KRW", "JPY", "EUR"])
@pytest.mark.parametrize("legacy_store", [False, True])
def test_synergy_results_record_the_simulation_currency_and_keep_legacy_results_unknown(town, currency, legacy_store):
    from store_emulator.domain.town import VLMSynergyResult
    store = Store.model_validate_json((SAMPLE / "store.json").read_text())
    store.currency = None if legacy_store else currency
    store.weekly_schedule = [DaySchedule(day=Weekday.WED, is_open=True, open_hour=9, close_hour=10)]
    pool = [Persona.model_validate(p) for p in json.loads((SAMPLE / "personas.json").read_text())][:300]
    result = asyncio.run(vlm_basket_synergy(
        town, "cafe-next-door", store, pool, config=SimulationConfig(currency=currency, seed=5), engine=_RecordingEngine(),
        pathfinder=AStarPathFinder(), cue_sampler=sample_cue, patterns=BEHAVIOR_PATTERNS, customers=4,
    ))
    saved = json.loads(result.model_dump_json())
    assert saved["currency"] == currency
    assert VLMSynergyResult.model_validate(saved).model_dump()["currency"] == currency
    del saved["currency"]
    assert VLMSynergyResult.model_validate(saved).model_dump()["currency"] is None
