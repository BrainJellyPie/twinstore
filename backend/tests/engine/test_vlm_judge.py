"""VLM shoppers judging a layout search: surrogate calibration, judging, winner, cancel — with a
scripted fake VLM (no server)."""

import asyncio
import json
from pathlib import Path

import pytest
from pydantic import BaseModel

from store_emulator.application.presets.behavior import BEHAVIOR_PATTERNS, sample_cue
from store_emulator.domain.config import EngineType, SimulationConfig
from store_emulator.domain.optimize import (
    ImpulseProfile,
    JudgeSpec,
    OptimizeObjective,
    OptimizeScope,
    OptimizeSpec,
)
from store_emulator.domain.persona import Persona
from store_emulator.domain.store import Store
from store_emulator.domain.types import TokenUsage
from store_emulator.engine.optimize.evaluate import select_personas, store_fingerprint
from store_emulator.engine.optimize.judge import (
    OptimizationCanceled,
    calibrate_surrogate,
    impulse_profile,
    judge_layout_search,
    profile_gap,
)
from store_emulator.engine.routing.pathfinder import AStarPathFinder
from store_emulator.engine.simulation.engines.vlm_glance import VLMGlanceEngine
from store_emulator.engine.simulation.engines.vlm_glance.prompt import EntryDecision
from store_emulator.engine.simulation.factory import build_engine
from store_emulator.engine.simulation.simulator import PerCustomerSimulationRunner

SAMPLE = Path(__file__).resolve().parents[2] / "sample_data" / "proj_67916afd" / "runs" / "run_ab0039" / "input"


@pytest.fixture(scope="module")
def store() -> Store:
    return Store.model_validate(json.loads((SAMPLE / "store.json").read_text()))


@pytest.fixture(scope="module")
def personas() -> list[Persona]:
    return [Persona.model_validate(p) for p in json.loads((SAMPLE / "personas.json").read_text())]


class FakeShopperVLM:
    """Plans one drink; at every shelf it is tempted (interest 8) by the product badged #1."""

    def __init__(self) -> None:
        self.calls = 0  # over the fake's lifetime
        self.run_calls = 0  # since the last reset_usage (one simulation run)

    def _answer[T: BaseModel](self, response_model: type[T]) -> T:
        self.calls += 1
        self.run_calls += 1
        if issubclass(response_model, EntryDecision):
            return response_model.model_validate({"mission": "a drink", "enter": True,
                                                  "items": [{"category": "Drink", "product": "", "qty": 1}]})
        return response_model.model_validate({"product": "", "number": 1, "interest": 8, "reason": "tempting"})

    async def generate_structured_async[T: BaseModel](
        self, response_model: type[T], system_prompt: str, user_prompt: str,
        *, max_retries: int = 1, seed: int | None = None, route: str | None = None, max_tokens: int | None = None,
    ) -> T:
        return self._answer(response_model)

    async def generate_structured_with_image_async[T: BaseModel](
        self, response_model: type[T], system_prompt: str, user_prompt: str, image_url: str,
        *, max_retries: int = 1, seed: int | None = None, route: str | None = None, max_tokens: int | None = None,
    ) -> T:
        return self._answer(response_model)

    def reset_usage(self) -> None:
        self.run_calls = 0

    def get_usage(self) -> TokenUsage:
        return TokenUsage(requests=self.run_calls)


def _vlm_config() -> SimulationConfig:
    cfg = SimulationConfig(engine_type=EngineType.VLM_GLANCE, seed=4)
    vlm = cfg.engines.vlm_glance.model_copy(update={"glance_policy": "all", "max_glances": 3, "image_width": 256})
    return cfg.model_copy(update={"engines": cfg.engines.model_copy(update={"vlm_glance": vlm})})


def test_impulse_profile_and_gap(store: Store, personas: list[Persona]):
    pf = AStarPathFinder()
    config = SimulationConfig(engine_type=EngineType.RULE_BASED, seed=1)
    runner = PerCustomerSimulationRunner(config, build_engine(config, pathfinder=pf), pf, sample_cue, BEHAVIOR_PATTERNS)
    _, customers = asyncio.run(runner.run(store.model_copy(deep=True), personas[:120]))
    profile = impulse_profile(store, customers)
    assert profile.impulse_rate > 0 and 0 < profile.impulse_revenue_share < 1
    assert set(profile.level_distribution) == {1, 2, 3, 4}
    assert sum(profile.level_distribution.values()) == pytest.approx(1.0, abs=1e-3)
    assert profile_gap(profile, profile) == 0
    flat = ImpulseProfile(impulse_rate=profile.impulse_rate * 3, impulse_revenue_share=0.0, level_distribution={})
    assert profile_gap(profile, flat) > 1


def test_calibration_fits_the_surrogate_to_the_pilot(store: Store, personas: list[Persona]):
    """A 'VLM' pilot that buys on impulse three times as often: the fit must close most of the gap."""
    pf = AStarPathFinder()
    panel = select_personas(personas, 120, seed=0)
    eager = SimulationConfig(engine_type=EngineType.RULE_BASED, seed=2)
    eager = eager.model_copy(update={"engines": eager.engines.model_copy(update={
        "rule_based": eager.engines.rule_based.model_copy(update={"impulse_base": 0.18})})})
    runner = PerCustomerSimulationRunner(eager, build_engine(eager, pathfinder=pf), pf, sample_cue, BEHAVIOR_PATTERNS)
    _, pilot = asyncio.run(runner.run(store.model_copy(deep=True), panel))
    base = SimulationConfig(engine_type=EngineType.RULE_BASED, seed=2)
    fitted, report = asyncio.run(calibrate_surrogate(store, base, panel, sample_cue, BEHAVIOR_PATTERNS, pf, pilot))
    assert report.gap_after < report.gap_before / 2
    assert report.impulse_base_after > report.impulse_base_before
    assert fitted.engines.rule_based.impulse_base == report.impulse_base_after
    assert fitted.perception.level_attention == report.level_attention_after
    assert report.grid_points == 27 and report.pilot_customers == len(pilot)


def test_vlm_judge_picks_a_winner_among_surrogate_candidates(store: Store, personas: list[Persona]):
    pf = AStarPathFinder()
    vlm_config = _vlm_config()
    spec = OptimizeSpec(objective=OptimizeObjective.REVENUE_PER_VISITOR, scope=OptimizeScope.PLANOGRAM,
                        budget=8, eval_customers=60, seed=3)
    judge = JudgeSpec(judge="vlm", vlm_customers=10, top_k=3, calibrate=True)
    search = select_personas(personas, spec.eval_customers, seed=spec.seed)
    panel = select_personas(search, judge.vlm_customers, seed=spec.seed + 2)
    phases: list[str] = []
    llm = FakeShopperVLM()
    result = asyncio.run(judge_layout_search(
        store, spec, judge, surrogate_config=vlm_config.model_copy(update={"engine_type": EngineType.RULE_BASED}),
        vlm_config=vlm_config, vlm_engine=VLMGlanceEngine(llm=llm, pathfinder=pf, config=vlm_config),
        search_personas=search, vlm_personas=panel, cue_sampler=sample_cue, patterns=BEHAVIOR_PATTERNS,
        pathfinder=pf, model_label="fake", on_phase=phases.append,
    ))
    report = result.judge
    assert report is not None and report.model == "fake" and report.customers == 10
    labels = [c.label for c in report.candidates]
    assert labels[0] == "baseline" and len(labels) == len(set(labels)) == 1 + judge.top_k
    assert phases[:2] == ["calibrating", "searching"] and phases[2:] == [f"judging {k}/4" for k in (2, 3, 4)]
    assert report.calibration is not None and report.calibration.gap_after <= report.calibration.gap_before
    assert sum(c.winner for c in report.candidates) == 1
    winner = next(c for c in report.candidates if c.winner)
    assert report.winner == winner.label
    assert all(c.vlm_score is not None and c.vlm_rank is not None for c in report.candidates)
    best_vlm = max(c.vlm_score or 0.0 for c in report.candidates)
    assert winner.vlm_score == best_vlm and result.best_score == best_vlm
    assert result.baseline_score == report.candidates[0].vlm_score
    assert report.spearman is not None and -1.0 <= report.spearman <= 1.0
    assert all(c.delta_mean is not None and c.prob_better is not None for c in report.candidates[1:])
    if winner.label == "baseline":
        assert store_fingerprint(result.best_store) == store_fingerprint(store) and result.applied_moves == []
    else:
        assert result.applied_moves == winner.moves and result.validation is not None
        assert result.validation.paired_customers == 10
    assert result.top_candidates == [] and "top_candidates" not in result.model_dump()
    assert llm.calls > 0 and report.vlm_requests == llm.calls


def test_vlm_judge_can_be_canceled(store: Store, personas: list[Persona]):
    pf = AStarPathFinder()
    vlm_config = _vlm_config()
    spec = OptimizeSpec(budget=3, eval_customers=20, seed=1)
    with pytest.raises(OptimizationCanceled):
        asyncio.run(judge_layout_search(
            store, spec, JudgeSpec(judge="vlm", vlm_customers=4, top_k=1),
            surrogate_config=vlm_config, vlm_config=vlm_config,
            vlm_engine=VLMGlanceEngine(llm=FakeShopperVLM(), pathfinder=pf, config=vlm_config),
            search_personas=personas[:20], vlm_personas=personas[:4], cue_sampler=sample_cue,
            patterns=BEHAVIOR_PATTERNS, pathfinder=pf, should_stop=lambda: True,
        ))


def test_stop_ends_a_vision_layout_run_without_waiting_for_it(store: Store, personas: list[Persona]):
    import time as _time

    class _SlowVLM(FakeShopperVLM):
        async def generate_structured_with_image_async(self, *a, **k):  # type: ignore[override]
            await asyncio.sleep(30)          # a slow local model: one layout run would take minutes
            return await super().generate_structured_with_image_async(*a, **k)

        async def generate_structured_async(self, *a, **k):  # type: ignore[override]
            await asyncio.sleep(30)
            return await super().generate_structured_async(*a, **k)

    pf = AStarPathFinder()
    vlm_config = _vlm_config()
    started = _time.monotonic()
    stop_at = started + 1.5
    with pytest.raises(OptimizationCanceled, match="while judging baseline"):
        asyncio.run(judge_layout_search(
            store, OptimizeSpec(budget=3, eval_customers=20, seed=1), JudgeSpec(judge="vlm", vlm_customers=4, top_k=1, calibrate=True),
            surrogate_config=vlm_config, vlm_config=vlm_config,
            vlm_engine=VLMGlanceEngine(llm=_SlowVLM(), pathfinder=pf, config=vlm_config),
            search_personas=personas[:20], vlm_personas=personas[:4], cue_sampler=sample_cue,
            patterns=BEHAVIOR_PATTERNS, pathfinder=pf, should_stop=lambda: _time.monotonic() > stop_at,
        ))
    assert _time.monotonic() - started < 10
