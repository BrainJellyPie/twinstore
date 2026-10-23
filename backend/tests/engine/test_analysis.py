import numpy as np

from store_emulator.application.pos import parse_pos_csv
from store_emulator.domain.customer import CustomerResult, TimelineEvent
from store_emulator.domain.persona import Persona
from store_emulator.domain.types import Action, Weekday
from store_emulator.engine.analysis.compare import compare_runs, required_n
from store_emulator.engine.analysis.fidelity import (
    PosLine,
    fidelity_report,
    js_divergence,
    ndcg,
    spearman,
    wasserstein_1d,
)
from store_emulator.engine.simulation.aggregator import aggregate


def _customer(pid: str, buys: list[tuple[str, int, int, str]], hour: str = "12") -> CustomerResult:
    timeline = [TimelineEvent(elapsed_sec=0, x=0, y=2, action=Action.ENTER)]
    t = 0
    for sku, price, qty, origin in buys:
        t += 1
        timeline.append(TimelineEvent(elapsed_sec=t, x=1, y=1, action=Action.MOVE))
        timeline.append(TimelineEvent(
            elapsed_sec=t, x=1, y=0, action=Action.BUY, duration=3, target_rack="A",
            product_sku=sku, product_name=sku, price=price, quantity=qty, origin=origin,
        ))
    timeline.append(TimelineEvent(elapsed_sec=t + 3, x=4, y=2, action=Action.PAY, duration=1))
    timeline.append(TimelineEvent(elapsed_sec=t + 5, x=4, y=2, action=Action.EXIT))
    return CustomerResult(
        persona_id=pid, day=Weekday.MON, arrival_time=f"{hour}:00:00", timeline=timeline,
        total_spent=sum(p * q for _, p, q, _ in buys),
    )


def _persona(pid: str, age: str) -> Persona:
    return Persona(id=pid, identity="x", age_group=age, gender="Male", description="", intent="", purpose="p")  # type: ignore[arg-type]


def test_aggregate_funnel_and_impulse_kpis(collision_store):
    results = [
        _customer("a", [("sku-a", 100, 2, "planned"), ("sku-b", 200, 1, "impulse")]),
        _customer("b", []),
    ]
    personas = [_persona("a", "20s"), _persona("b", "30s")]
    agg = aggregate(collision_store, results, personas, [[0.0] * 5 for _ in range(3)])
    s = agg.summary
    assert (s.total_customers, s.buyers, s.total_revenue, s.units_sold) == (2, 1, 400, 3)
    assert s.conversion_rate == 0.5
    assert s.impulse_revenue_share == 0.5
    assert s.segments["age_group"]["20s"].conversion_rate == 1.0
    assert s.segments["age_group"]["30s"].conversion_rate == 0.0
    assert s.racks[0].units == 3 and s.racks[0].impulse_units == 1
    assert sum(map(sum, agg.dwell_heatmap)) > 0


def test_compare_identical_runs_has_zero_effect():
    runs = [_customer(str(i), [("sku-a", 100 + i, 1, "planned")]) for i in range(50)]
    report = compare_runs(runs, runs, n_bootstrap=300)
    spend = next(m for m in report.metrics if m.metric == "spend")
    assert spend.diff == 0 and spend.ci_low == 0 and spend.ci_high == 0
    assert spend.prob_b_greater == 0 and spend.prob_b_less == 0


def test_compare_detects_a_consistent_lift():
    a = [_customer(str(i), [("sku-a", 100 + i, 1, "planned")]) for i in range(80)]
    b = [_customer(str(i), [("sku-a", 110 + i, 1, "planned")]) for i in range(80)]
    spend = next(m for m in compare_runs(a, b, n_bootstrap=300).metrics if m.metric == "spend")
    assert spend.diff == 10 and spend.ci_low > 0 and spend.prob_b_greater == 1.0
    assert spend.prob_b_less == 0


def test_required_n_scales_with_variance():
    assert required_n(10, 100) < required_n(20, 100)
    assert required_n(0, 100) == 0


def test_distribution_metrics():
    p = np.array([1.0, 2.0, 3.0])
    assert js_divergence(p, p) == 0
    assert abs(js_divergence(np.array([1.0, 0.0]), np.array([0.0, 1.0])) - 1.0) < 1e-9
    assert spearman(p, p * 10) == 1.0
    assert ndcg(p, p, 3) == 1.0
    assert wasserstein_1d([1, 2, 3], [1, 2, 3]) == 0
    assert abs(wasserstein_1d([0, 0], [1, 1]) - 1.0) < 1e-9


def test_fidelity_report_on_matching_sales(collision_store):
    results = [_customer(str(i), [("sku-a", 100, 1, "planned")] if i % 3 else [("sku-b", 200, 1, "planned")]) for i in range(30)]
    pos = [PosLine(transaction_id=r.persona_id, sku=e.product_sku, quantity=1, unit_price=e.price, hour=12)
           for r in results for e in r.purchases]
    report = fidelity_report(collision_store, results, pos)
    values = {m.name: m.value for m in report.metrics}
    assert values["sku_js_similarity"] == 1.0
    assert values["basket_units_w1"] == 0.0
    assert values["hourly_js_similarity"] == 1.0


def test_parse_pos_csv_accepts_common_aliases():
    csv_text = "BASKET_ID,PRODUCT_ID,QUANTITY,SALES_VALUE,TRANS_TIME\n1,sku-a,2,300,1631\n1,sku-b,1,200,1631\n"
    lines = parse_pos_csv(csv_text.encode(), "pos.csv")
    assert [(ln.sku, ln.quantity, ln.unit_price, ln.hour) for ln in lines] == [("sku-a", 2, 150, 16), ("sku-b", 1, 200, 16)]


def test_impulse_spend_is_not_compared_with_a_run_that_never_recorded_it():
    new = [_customer(f"P{i}", [("cola", 200, 1, "impulse")]) for i in range(40)]
    old = [_customer(f"P{i}", [("cola", 200, 1, "")]) for i in range(40)]   # an older version: no origin
    report = compare_runs(new, old, run_a="run_new", run_b="run_old", n_bootstrap=200)
    assert "impulse_spend" not in {m.metric for m in report.metrics}
    assert any("run_old was made by an older version" in note for note in report.notes)
    both = compare_runs(new, new, n_bootstrap=200)
    assert "impulse_spend" in {m.metric for m in both.metrics} and not any("older version" in n for n in both.notes)
