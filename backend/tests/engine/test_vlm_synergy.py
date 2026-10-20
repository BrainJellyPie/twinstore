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
from store_emulator.domain.store import Store
from store_emulator.domain.town import Town, TownArrival, TownSpec, VenueCategory
from store_emulator.domain.types import TokenUsage
from store_emulator.engine.routing.pathfinder import AStarPathFinder
from store_emulator.engine.simulation.engines.vlm_glance import VLMGlanceEngine
from store_emulator.engine.simulation.engines.vlm_glance.prompt import EntryDecision
from store_emulator.engine.town import (
    counterfactual_arrival,
    estimate_demand,
    generate_town,
    place_venue,
    town_context_text,
)
from store_emulator.engine.town.vlm_synergy import vlm_basket_synergy

SAMPLE = Path(__file__).resolve().parents[2] / "sample_data" / "proj_67916afd" / "runs" / "run_ab0039" / "input"


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
