import asyncio
import json
from pathlib import Path

from store_emulator.application.presets.behavior import BEHAVIOR_PATTERNS, sample_cue
from store_emulator.domain.config import EngineType, SimulationConfig
from store_emulator.domain.engine import EngineDecision, PerCustomerContext
from store_emulator.domain.persona import Persona
from store_emulator.domain.store import Store
from store_emulator.domain.types import TokenUsage, stable_seed
from store_emulator.engine.generators.arrivals import generate_customers
from store_emulator.engine.routing.pathfinder import AStarPathFinder
from store_emulator.engine.simulation.factory import build_engine
from store_emulator.engine.simulation.simulator import PerCustomerSimulationRunner

SAMPLE = Path(__file__).resolve().parents[2] / "sample_data" / "proj_67916afd" / "runs"


def _sample(run: str, n: int = 120) -> tuple[Store, list[Persona]]:
    store = Store.model_validate(json.loads((SAMPLE / run / "input" / "store.json").read_text()))
    personas = [Persona.model_validate(p) for p in json.loads((SAMPLE / run / "input" / "personas.json").read_text())]
    return store, personas[:n]


def _run(store: Store, personas: list[Persona], **cfg: object):
    config = SimulationConfig.model_validate({"engine_type": EngineType.RULE_BASED, **cfg})
    pf = AStarPathFinder()
    runner = PerCustomerSimulationRunner(config, build_engine(config, pathfinder=pf), pf, sample_cue, BEHAVIOR_PATTERNS)
    return asyncio.run(runner.run(store, personas, max_concurrent=8))


def test_stable_seed_is_deterministic_and_order_sensitive():
    assert stable_seed(1, "a") == stable_seed(1, "a")
    assert stable_seed(1, "a") != stable_seed("a", 1)
    assert 0 <= stable_seed("x") < 2**63


def test_arrivals_do_not_depend_on_who_else_is_in_the_run():
    _, personas = _sample("run_ab0039", 50)
    full = {e.persona_id: e.arrival_time for e in generate_customers(personas, seed=7)}
    half = {e.persona_id: e.arrival_time for e in generate_customers(personas[::2], seed=7)}
    assert all(full[pid] == t for pid, t in half.items())
    other = {e.persona_id: e.arrival_time for e in generate_customers(personas, seed=8)}
    assert other != full


def test_same_seed_reproduces_a_run_exactly():
    store, personas = _sample("run_ab0039")
    a_agg, a = _run(store, personas, seed=3)
    b_agg, b = _run(store, personas, seed=3)
    assert [r.model_dump() for r in a] == [r.model_dump() for r in b]
    assert a_agg.summary == b_agg.summary


def test_replicates_differ():
    store, personas = _sample("run_ab0039")
    _, a = _run(store, personas, seed=3, replicate=0)
    _, b = _run(store, personas, seed=3, replicate=1)
    assert [r.total_spent for r in a] != [r.total_spent for r in b]


class _RecordingEngine:
    engine_type = "recording"

    def __init__(self) -> None:
        self.contexts: dict[str, PerCustomerContext] = {}

    def reset_usage(self) -> None:
        pass

    def get_usage(self) -> TokenUsage:
        return TokenUsage()

    async def decide_actions(self, context: PerCustomerContext) -> EngineDecision:
        self.contexts[context.persona.id] = context
        return EngineDecision(actions=[], engine_type=self.engine_type)


def test_common_random_numbers_across_layouts():
    """Same persona + seed → same cue and engine seed, whatever the layout."""
    store_a, personas = _sample("run_ab0039", 40)
    store_b, _ = _sample("run_efd57c", 40)
    seen: list[dict[str, PerCustomerContext]] = []
    for store in (store_a, store_b):
        engine = _RecordingEngine()
        config = SimulationConfig(seed=11)
        pf = AStarPathFinder()
        runner = PerCustomerSimulationRunner(config, engine, pf, sample_cue, BEHAVIOR_PATTERNS)
        asyncio.run(runner.run(store, personas))
        seen.append(engine.contexts)
    a, b = seen
    assert a.keys() == b.keys()
    for pid in a:
        assert a[pid].cue == b[pid].cue
        assert a[pid].seed == b[pid].seed


def test_failures_are_recorded_not_silently_dropped():
    class _Failing(_RecordingEngine):
        async def decide_actions(self, context: PerCustomerContext) -> EngineDecision:
            raise RuntimeError("boom")

    store, personas = _sample("run_ab0039", 5)
    config = SimulationConfig()
    pf = AStarPathFinder()
    runner = PerCustomerSimulationRunner(config, _Failing(), pf, sample_cue, BEHAVIOR_PATTERNS)
    progress: list[tuple[int, int, int]] = []
    agg, results = asyncio.run(runner.run(store, personas, on_progress=lambda c, f, t: progress.append((c, f, t))))
    assert results == []
    assert agg.diagnostics.requested_customers == 5
    assert len(agg.diagnostics.failed_customers) == 5
    assert "boom" in agg.diagnostics.failed_customers[0].reason
    assert progress[-1] == (5, 5, 5)
