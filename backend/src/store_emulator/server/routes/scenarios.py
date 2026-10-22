"""Scenario presets and a live preview of a scenario's effects."""

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from starlette.concurrency import run_in_threadpool

from store_emulator.application import scenarios as service
from store_emulator.application.errors import AppError
from store_emulator.application.scenarios import PRESETS, DescribeRequest
from store_emulator.domain.scenario import Scenario, ScenarioPriors
from store_emulator.engine.scenario import compile_scenario

from ..deps import get_config

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


def _view(scenario: Scenario, priors: ScenarioPriors | None = None) -> ScenarioEffectsView:
    fx = compile_scenario(scenario, priors)
    return ScenarioEffectsView(
        situation=fx.situation, traffic=round(fx.base_traffic, 3),
        traffic_by_hour={h: round(v, 3) for h, v in sorted(fx.traffic_by_hour.items())},
        demand={k: round(v, 3) for k, v in sorted(fx.demand.items()) if abs(v - 1.0) > 1e-3},
        impulse=round(fx.impulse, 3), dwell=round(fx.dwell, 3), walkout=round(fx.walkout, 3),
        budget=round(fx.budget, 3), quantity=round(fx.quantity, 3),
    )


@router.get("/scenarios", summary="Scenario presets with their compiled effects", response_model=list[ScenarioPreset])
async def list_scenarios(project_id: str = "", setup_id: str = "") -> list[ScenarioPreset]:
    """With a layout (`project_id` and `setup_id`), effects use its store format's effect sizes, as its runs do."""
    priors = await run_in_threadpool(service.layout_priors, project_id, setup_id, get_config())
    return [ScenarioPreset(scenario=s, effects=_view(s, priors)) for s in PRESETS]


@router.post("/scenarios/preview", summary="Compile a custom scenario", response_model=ScenarioEffectsView)
async def preview_scenario(scenario: Scenario, project_id: str = "", setup_id: str = "") -> ScenarioEffectsView:
    """Effects of a scenario without running anything (for the scenario editor); with a layout, at its effect sizes."""
    priors = await run_in_threadpool(service.layout_priors, project_id, setup_id, get_config())
    return _view(scenario, priors)


class DescribedScenarioView(BaseModel):
    scenario: Scenario
    effects: ScenarioEffectsView
    warnings: list[str] = []


@router.post("/scenarios/describe", summary="Set up a scenario from a description", response_model=DescribedScenarioView)
async def describe_scenario(req: DescribeRequest) -> DescribedScenarioView:
    """The text model turns a plain description of the day into a custom scenario. With a layout, promotions and
    stock-outs are checked against its products; targets that match nothing are dropped and listed in `warnings`."""
    def run() -> DescribedScenarioView:
        try:
            described = service.describe(req, get_config())
        except AppError as e:
            raise HTTPException(e.status_code, e.message) from e
        priors = service.layout_priors(req.project_id, req.setup_id, get_config())
        return DescribedScenarioView(scenario=described.scenario, effects=_view(described.scenario, priors),
                                     warnings=described.warnings)

    return await run_in_threadpool(run)
