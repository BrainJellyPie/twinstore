"""Search scores cannot silently change their shopper panel after failures."""

import asyncio

import pytest

from store_emulator.domain.engine import EngineDecision, PerCustomerContext
from store_emulator.domain.optimize import OptimizeObjective
from tests.engine.test_optimize import _evaluator, pathfinder, personas, store  # noqa: F401


@pytest.mark.parametrize("objective", list(OptimizeObjective))
@pytest.mark.parametrize("size", [2, 9])
@pytest.mark.parametrize("missing", ["first", "last", "all_but_last"])
def test_partial_search_results_are_rejected_without_poisoning_cache(
    store, personas, pathfinder, monkeypatch, objective, size, missing,
):
    evaluator = _evaluator(personas, pathfinder, size, objective)
    healthy = asyncio.run(_evaluator(personas, pathfinder, size, objective).evaluate(store))
    selected = evaluator.personas
    lost = selected[:1] if missing == "first" else selected[-1:] if missing == "last" else selected[:-1]
    failed_ids = {p.id for p in lost}
    original = evaluator._engine.decide_actions

    async def partial(context: PerCustomerContext) -> EngineDecision:
        if context.persona.id in failed_ids:
            raise RuntimeError("scripted shopper failure")
        return await original(context)

    monkeypatch.setattr(evaluator._engine, "decide_actions", partial)
    with pytest.raises(RuntimeError, match=rf"{len(lost)} of {size} shoppers failed.*scripted shopper failure"):
        asyncio.run(evaluator.evaluate(store))
    assert evaluator.evaluations == evaluator.cache_hits == 0

    monkeypatch.setattr(evaluator._engine, "decide_actions", original)
    recovered = asyncio.run(evaluator.evaluate(store))
    assert recovered == healthy
    assert evaluator.evaluations == 1 and evaluator.cache_hits == 0
    assert asyncio.run(evaluator.evaluate(store)) == recovered
    assert evaluator.evaluations == 1 and evaluator.cache_hits == 1


@pytest.mark.parametrize("method", ["simulate", "evaluate_customers"])
def test_paired_comparisons_keep_partial_results_for_common_panel_selection(
    store, personas, pathfinder, monkeypatch, method,
):
    evaluator = _evaluator(personas, pathfinder, 3)
    lost = evaluator.personas[0].id
    original = evaluator._engine.decide_actions

    async def partial(context: PerCustomerContext) -> EngineDecision:
        if context.persona.id == lost:
            raise RuntimeError("scripted shopper failure")
        return await original(context)

    monkeypatch.setattr(evaluator._engine, "decide_actions", partial)
    if method == "simulate":
        _, aggregated, customers = asyncio.run(evaluator.simulate(store))
        assert [f.persona_id for f in aggregated.diagnostics.failed_customers] == [lost]
    else:
        customers = asyncio.run(evaluator.evaluate_customers(store, evaluator.personas))
    assert {c.persona_id for c in customers} == {p.id for p in evaluator.personas[1:]}


def test_successful_nonbuyers_still_receive_a_real_zero_score(store, personas, pathfinder, monkeypatch):
    evaluator = _evaluator(personas, pathfinder, 3)

    async def leave_without_buying(context: PerCustomerContext) -> EngineDecision:
        return EngineDecision(actions=[], engine_type="rule_based")

    monkeypatch.setattr(evaluator._engine, "decide_actions", leave_without_buying)
    score, summary = asyncio.run(evaluator.evaluate(store))
    assert score == 0 and summary.total_customers == 3
    assert evaluator.evaluations == 1
