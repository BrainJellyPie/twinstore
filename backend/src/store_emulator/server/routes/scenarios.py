"""Scenario presets and a live preview of a scenario's effects."""

from fastapi import APIRouter
from pydantic import BaseModel

from store_emulator.application.scenarios import PRESETS
from store_emulator.domain.scenario import Scenario
from store_emulator.engine.scenario import compile_scenario

router = APIRouter(prefix="/api", tags=["scenarios"])


class ScenarioEffectsView(BaseModel):
    situation: str
    traffic: float                     # whole-day multiplier
    traffic_by_hour: dict[int, float]  # extra multipliers on top, by hour
    demand: dict[str, float]           # category → multiplier (only changed categories)
    impulse: float
    dwell: float
    walkout: float
    budget: float
    quantity: float


class ScenarioPreset(BaseModel):
    scenario: Scenario
    effects: ScenarioEffectsView


def _view(scenario: Scenario) -> ScenarioEffectsView:
    fx = compile_scenario(scenario)
    return ScenarioEffectsView(
        situation=fx.situation, traffic=round(fx.base_traffic, 3),
        traffic_by_hour={h: round(v, 3) for h, v in sorted(fx.traffic_by_hour.items())},
        demand={k: round(v, 3) for k, v in sorted(fx.demand.items()) if abs(v - 1.0) > 1e-3},
        impulse=round(fx.impulse, 3), dwell=round(fx.dwell, 3), walkout=round(fx.walkout, 3),
        budget=round(fx.budget, 3), quantity=round(fx.quantity, 3),
    )


@router.get("/scenarios", summary="Scenario presets with their compiled effects", response_model=list[ScenarioPreset])
async def list_scenarios() -> list[ScenarioPreset]:
    return [ScenarioPreset(scenario=s, effects=_view(s)) for s in PRESETS]


@router.post("/scenarios/preview", summary="Compile a custom scenario", response_model=ScenarioEffectsView)
async def preview_scenario(scenario: Scenario) -> ScenarioEffectsView:
    """Effects of a scenario without running anything (for the scenario editor)."""
    return _view(scenario)
