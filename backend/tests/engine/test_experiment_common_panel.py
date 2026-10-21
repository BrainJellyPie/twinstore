"""Partial simulation failures must not change the population used to select an experiment winner."""

import asyncio

import pytest

from store_emulator.domain.customer import CustomerResult, TimelineEvent
from store_emulator.domain.persona import Persona
from store_emulator.domain.types import Action, Weekday
from store_emulator.engine.layout_gen import generate_store
from store_emulator.engine.marketing.experiment import run_experiment
from store_emulator.engine.optimize.evaluate import LayoutEvaluator


def run_case(monkeypatch, populations):
    store = generate_store("mini_mart")
    panel = [Persona(id=f"p{i}", identity="Shopper", age_group="20s", gender="Female",
                     description="Tea", intent="tea", purpose="tea") for i in range(40)]
    pending = iter(populations)

    async def evaluate(self, store, panel):
        values = next(pending)
        return [CustomerResult(
            persona_id=pid, day=Weekday.MON, arrival_time="12:00:00", total_spent=value,
            timeline=[TimelineEvent(elapsed_sec=1, x=1, y=1, action=Action.BUY, target_rack="shelf",
                                    product_sku="tea", product_name="Tea", price=value)] if value else [],
        ) for pid, value in values.items()]

    monkeypatch.setattr(LayoutEvaluator, "evaluate_customers", evaluate)
    evaluator = object.__new__(LayoutEvaluator)
    arms = [(f"Variant {i}", store, [], []) for i in range(1, len(populations))]
    return asyncio.run(run_experiment(evaluator, store, arms, panel, ["tea"]))


def test_winner_and_all_report_metrics_use_one_common_population(monkeypatch):
    base = {f"p{i}": 100 if i < 20 else 0 for i in range(40)}
    candidate1 = {f"p{i}": 200 for i in range(20)}
    candidate2 = {f"p{i}": 150 if i < 20 else 1000 for i in range(40)}
    control, variants, winner = run_case(monkeypatch, [base, candidate1, candidate2])
    assert winner == "Variant 1"
    assert control.revenue_per_visitor == 100
    assert [v.revenue_per_visitor for v in variants] == [200, 150]
    for arm in [control, *variants]:
        assert arm.customers == 20
        assert arm.warnings
        assert arm.top_skus[0].revenue == 20 * arm.revenue_per_visitor
    for variant in variants:
        spend = next(m for m in variant.vs_control if m.metric == "spend")
        assert spend.mean_a == control.revenue_per_visitor
        assert spend.mean_b == variant.revenue_per_visitor
        focus = next(f for f in variant.focus if f.metric == "spend")
        assert focus.control == control.revenue_per_visitor
        assert focus.variant == variant.revenue_per_visitor
        assert variant.segments and all(s.n == 20 for s in variant.segments)


@pytest.mark.parametrize("populations", [
    [{}, {"p0": 10}],
    [{"p0": 10}, {}],
    [{"p0": 10}, {"p1": 20}],
    [{"p0": 10, "p1": 10}, {"p0": 20}, {"p1": 20}],
])
def test_uncomparable_experiment_fails_instead_of_reporting_zero_sales(monkeypatch, populations):
    with pytest.raises(ValueError, match="successful|common|paired"):
        run_case(monkeypatch, populations)


@pytest.mark.parametrize("value", [0, 100])
def test_complete_population_keeps_valid_zero_and_nonzero_results(monkeypatch, value):
    population = {f"p{i}": value for i in range(40)}
    control, variants, winner = run_case(monkeypatch, [population, population])
    assert winner == ""
    assert control.revenue_per_visitor == variants[0].revenue_per_visitor == value
    assert control.customers == variants[0].customers == 40
    assert control.warnings == variants[0].warnings == []
    assert all(m.diff == m.ci_low == m.ci_high == 0 for m in variants[0].vs_control)
