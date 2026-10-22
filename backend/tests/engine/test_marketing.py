"""Marketing studio offline: layout variants, a paired A/B run with the rule engine, and survey answers from a
fake vision model aggregated into scales, price points and preference shares."""

import asyncio
import json
from pathlib import Path

import pytest
from PIL import Image
from pydantic import BaseModel

from store_emulator.domain.config import SimulationConfig
from store_emulator.domain.marketing import SurveyAnswer, VariantChange
from store_emulator.domain.optimize import OptimizeObjective
from store_emulator.domain.persona import Persona
from store_emulator.domain.store import Store
from store_emulator.domain.types import Face
from store_emulator.engine.marketing import (
    apply_changes,
    likert_summary,
    preference_shares,
    run_experiment,
    survey_panel,
    van_westendorp,
)
from store_emulator.engine.marketing.survey import response_model, stimulus_board
from store_emulator.engine.marketing.variants import charm_price
from store_emulator.engine.optimize.evaluate import LayoutEvaluator, select_personas
from store_emulator.engine.perception.shelf_render import render_face
from store_emulator.engine.routing.pathfinder import AStarPathFinder

SAMPLE = Path(__file__).resolve().parents[2] / "sample_data" / "proj_67916afd" / "runs" / "run_ab0039" / "input"
DRINK_1 = "r_b5cf7836"


@pytest.fixture(scope="module")
def store() -> Store:
    return Store.model_validate(json.loads((SAMPLE / "store.json").read_text()))


@pytest.fixture(scope="module")
def personas() -> list[Persona]:
    return [Persona.model_validate(p) for p in json.loads((SAMPLE / "personas.json").read_text())]


def _items(store: Store, sku: str):
    return [(r, s, i) for r in store.racks for s in r.slots for i in s.items if i.sku == sku]


def test_price_discount_promo_and_category_changes(store: Store) -> None:
    changes = [
        VariantChange(kind="price", sku="A0001", price=199),
        VariantChange(kind="discount", sku="A0002", percent=-20),
        VariantChange(kind="promo", sku="A0003", promo="1+1"),
        VariantChange(kind="category_price", category="snacks", percent=10, charm=True),
    ]
    out, applied, warnings = apply_changes(store, changes)
    assert not warnings and len(applied) == 4
    assert all(i.price == 199 and i.regular_price == 0 for _, _, i in _items(out, "A0001"))
    assert all(i.price == 199 and i.regular_price == 249 for _, _, i in _items(out, "A0002"))   # 249 − 20 %
    assert all(i.promo == "1+1" for _, _, i in _items(out, "A0003"))
    snacks = [i for r in out.racks if "snacks" in r.rack_name.lower() for s in r.slots for i in s.items]
    assert snacks and all(i.price % 100 == 99 for i in snacks)
    # the control is untouched
    assert all(i.price == 249 and not i.promo for _, _, i in _items(store, "A0002"))
    # .99 at or below the price (at or above with up=True); prices under .99, free ones among them, stay
    assert charm_price(274) == 199 and charm_price(274, up=True) == 299 and charm_price(299) == 299
    assert charm_price(1200, 1) == 1200 and charm_price(0) == 0 and charm_price(0, up=True) == 0 and charm_price(50) == 50


def _category_prices(store: Store, word: str) -> dict[str, tuple[int, int]]:
    return {i.sku: (i.price, i.regular_price) for r in store.racks if word in r.rack_name.lower() for s in r.slots for i in s.items}


@pytest.mark.parametrize("percent", [-10, -20, 0, 10, 50])
def test_charm_pricing_keeps_the_direction_of_a_category_change(store: Store, percent: int) -> None:
    free = store.model_copy(deep=True)
    drink = next(r for r in free.racks if "drink" in r.rack_name.lower())
    drink.slots[0].items[0].price = 0
    before = _category_prices(free, "drink")
    out, applied, warnings = apply_changes(free, [VariantChange(kind="category_price", category="Drink", percent=percent, charm=True)])
    after = _category_prices(out, "drink")
    assert not warnings and before
    for sku, (old, _) in before.items():
        new = after[sku][0]
        if old == 0:
            assert new == 0                      # a free product stays free
        elif percent <= 0:
            assert new <= old                    # a cut (or a plain charm ending) never raises a price
        else:
            assert new > old                     # a rise never becomes a cut
        assert old == 0 or new % 100 == 99 or new < 99
    ratios = [after[s][0] / old - 1 for s, (old, _) in before.items() if old > 0]
    assert f"{sum(ratios) / len(ratios) * 100:+.1f} % on average" in applied[0]   # what the prices really did


def test_category_price_change_keeps_the_old_price_as_the_reference(store: Store) -> None:
    before = _category_prices(store, "drink")
    out, applied, _ = apply_changes(store, [VariantChange(kind="category_price", category="Drink", percent=50)])
    after = _category_prices(out, "drink")
    assert applied and "shoppers remember the old prices" in applied[0]
    # Without a reference the rule engine's price factor is 1: a 50 % rise looked free to shoppers.
    assert all(after[s] == (round(p * 1.5), p) for s, (p, _) in before.items() if p > 0)
    # A discount first, then the category change: shoppers still remember the usual price.
    sku = next(iter(before))
    twice, _, _ = apply_changes(store, [VariantChange(kind="discount", sku=sku, percent=-20),
                                        VariantChange(kind="category_price", category="Drink", percent=10)])
    assert _category_prices(twice, "drink")[sku][1] == before[sku][0]


def test_category_price_rise_lowers_rule_shoppers_sales(store: Store, personas: list[Persona]) -> None:
    from store_emulator.application.presets.behavior import (
        BEHAVIOR_PATTERNS,
        sample_cue,
    )

    panel = select_personas(personas, 200, seed=3)
    evaluator = LayoutEvaluator(SimulationConfig(seed=3), panel, sample_cue, BEHAVIOR_PATTERNS, AStarPathFinder(),
                                OptimizeObjective.REVENUE_PER_VISITOR)
    drinks = list(_category_prices(store, "drink"))
    variant, applied, warnings = apply_changes(store, [VariantChange(kind="category_price", category="Drink", percent=50)])
    _, results, _ = asyncio.run(run_experiment(evaluator, store, [("Drinks +50 %", variant, applied, warnings)], panel, drinks))
    units = next(f for f in results[0].focus if f.sku == "*" and f.metric == "units")
    assert units.ci_high < 0 and units.rel_diff < -0.2


def _blocked_store() -> Store:
    path = Path(__file__).resolve().parents[2] / "sample_data" / "proj_67916afd" / "setups" / "setup_eaf5.json"
    return Store.model_validate(json.loads(path.read_text())["store"])


def test_move_to_a_face_shoppers_cannot_reach_warns_instead_of_dropping_the_product() -> None:
    from store_emulator.engine.layout_edit import apply_layout_edit
    from store_emulator.engine.validation import clear_blocked_slots

    walled = _blocked_store()   # Drink 1 (r_3592657b) stands with its W face against the outer wall
    to_wall = VariantChange(kind="move", sku="A0082", rack_id="r_3592657b", face="W", level=3)
    out, applied, warnings = apply_changes(walled, [to_wall])
    assert not applied and len(warnings) == 1 and "cannot reach the W face" in warnings[0] and "outer wall" in warnings[0]
    simulated = out.model_copy(deep=True)
    clear_blocked_slots(simulated)   # what the simulator does before shoppers walk in
    assert len(_items(simulated, "A0082")) == len(_items(walled, "A0082")) > 0
    # "Edit in words" on a saved layout uses the same edits: the problem comes back as a warning, nothing is raised.
    edited, edit_applied, problems = apply_layout_edit(walled, [to_wall], "USD")
    assert not edit_applied and problems == warnings
    assert len(_items(edited, "A0082")) == len(_items(walled, "A0082"))
    # The reachable face of the same rack still takes the product, and the simulation keeps it there.
    front, applied2, warnings2 = apply_changes(walled, [to_wall.model_copy(update={"face": "E"})])
    assert applied2 and not warnings2
    clear_blocked_slots(front)
    assert any(r.id == "r_3592657b" for r, _, _ in _items(front, "A0082"))


def test_move_to_eye_level_keeps_facings_and_unknown_skus_warn(store: Store) -> None:
    before = len(_items(store, "A0001"))
    out, applied, warnings = apply_changes(store, [VariantChange(kind="move", sku="A0001", rack_id="r_801fadeb", level=3)])
    assert applied and not warnings
    moved = _items(out, "A0001")
    assert len(moved) == before and any(r.id == "r_801fadeb" and s.level == 3 for r, s, _ in moved)
    assert sum(len(s.items) for r in out.racks for s in r.slots) == sum(len(s.items) for r in store.racks for s in r.slots)
    _, applied2, warnings2 = apply_changes(store, [VariantChange(kind="promo", sku="NOPE", promo="SALE")])
    assert not applied2 and "not in this layout" in warnings2[0]


def test_package_image_reaches_the_vision_shoppers_shelf(store: Store, tmp_path: Path) -> None:
    art = Image.new("RGBA", (120, 240), (0, 0, 0, 0))
    art.paste((20, 200, 90, 255), (20, 20, 100, 230))
    path = tmp_path / "pack.png"
    art.save(path)
    out, applied, _ = apply_changes(store, [VariantChange(kind="package", sku="A0001", asset_id="p1")],
                                    package_uris={"p1": f"file://{path}"})
    assert applied
    rack = next(r for r in out.racks if r.id == DRINK_1)
    face = next(s.face for s in rack.slots if any(i.sku == "A0001" for i in s.items))
    plain = render_face(next(r for r in store.racks if r.id == DRINK_1), Face(face))
    packed = render_face(rack, Face(face))
    assert plain.png != packed.png


def test_discount_sells_more_of_the_product_on_the_same_shoppers(store: Store, personas: list[Persona]) -> None:
    from store_emulator.application.presets.behavior import (
        BEHAVIOR_PATTERNS,
        sample_cue,
    )

    panel = select_personas(personas, 160, seed=3)
    evaluator = LayoutEvaluator(SimulationConfig(seed=3), panel, sample_cue, BEHAVIOR_PATTERNS, AStarPathFinder(),
                                OptimizeObjective.REVENUE_PER_VISITOR)
    focus = ["A0017"]
    variant, applied, warnings = apply_changes(store, [VariantChange(kind="discount", sku="A0017", percent=-50)])
    control, results, _ = asyncio.run(run_experiment(evaluator, store, [("Half price", variant, applied, warnings)], panel, focus))
    assert control.name == "Control" and len(results) == 1
    r = results[0]
    assert {m.metric for m in r.vs_control} >= {"spend", "units", "bought"}
    units = next(f for f in r.focus if f.sku == "A0017" and f.metric == "units")
    assert units.variant >= units.control and units.ci_low <= units.diff <= units.ci_high
    assert any(s.sku == "A0017" for s in r.top_skus)
    segs = {(s.segment, s.metric) for s in r.segments}
    assert ("gender Female", "spend") in segs and ("gender Male", "focus_units") in segs
    assert all(s.n >= 20 and s.ci_low <= s.diff <= s.ci_high for s in r.segments)


class _Fake:
    def __init__(self, answers: list[dict[str, object]]) -> None:
        self.answers = answers
        self.calls = 0

    async def generate_structured_with_image_async[T: BaseModel](
        self, response_model: type[T], system_prompt: str, user_prompt: str, image_url: str,
        *, max_retries: int = 1, seed: int | None = None, route: str | None = None,
    ) -> T:
        answer = self.answers[self.calls % len(self.answers)]
        self.calls += 1
        return response_model.model_validate(answer)


def test_survey_answers_and_aggregates(personas: list[Persona]) -> None:
    questions = ["purchase_intent", "appeal", "price_vw", "preference", "open"]
    model = response_model(questions, 2)
    assert {"purchase_intent_A", "purchase_intent_B", "appeal_A", "too_cheap", "preferred", "why"} <= set(model.model_fields)
    fake = _Fake([
        {"purchase_intent_A": 4, "purchase_intent_B": 2, "appeal_A": 5, "appeal_B": 3, "too_cheap": 0.9, "cheap": 1.5,
         "expensive": 2.5, "too_expensive": 3.5, "preferred": "A", "why": "bright and cold"},
        {"purchase_intent_A": 3, "purchase_intent_B": 4, "appeal_A": 3, "appeal_B": 4, "too_cheap": 1.0, "cheap": 1.8,
         "expensive": 2.8, "too_expensive": 4.0, "preferred": "B", "why": "cheaper looking"},
        {"purchase_intent_A": 5, "purchase_intent_B": 1, "appeal_A": 4, "appeal_B": 2, "too_cheap": 0.8, "cheap": 1.2,
         "expensive": 2.2, "too_expensive": 3.0, "preferred": "A", "why": ""},
    ])
    board = stimulus_board([Image.new("RGB", (200, 300), (200, 30, 30)), Image.new("RGB", (200, 300), (30, 30, 200))], ["Red", "Blue"])
    panel = select_personas(personas, 9, seed=0)
    answers = asyncio.run(survey_panel(fake, panel, board, questions, 2, currency="USD"))
    assert len(answers) == 9 and all(not a.error for a in answers)
    assert answers[0].purchase_intent == [4, 2] and answers[0].too_cheap == 90 and answers[1].preferred == 1

    intent_a = likert_summary([a.purchase_intent[0] for a in answers], "purchase_intent", 0)
    assert intent_a.n == 9 and intent_a.mean == 4.0 and intent_a.top2 == round(6 / 9, 4) and sum(intent_a.distribution) == 9
    shares = preference_shares([a.preferred for a in answers if a.preferred is not None], ["Red", "Blue"], 2)
    assert shares[0].share == round(6 / 9, 4) and shares[0].ci_low < shares[0].share < shares[0].ci_high
    price = van_westendorp(answers)
    assert price is not None and price.n == 9
    assert price.optimal_price_point is not None and 90 <= price.optimal_price_point <= 400


def test_van_westendorp_needs_consistent_answers() -> None:
    bad = [SurveyAnswer(respondent=str(i), age_group="20s", gender="Male", too_cheap=300, cheap=100, expensive=50, too_expensive=10)
           for i in range(10)]
    assert van_westendorp(bad) is None


@pytest.mark.parametrize("price", [float("inf"), 1e308])
def test_invalid_price_response_does_not_discard_other_respondents(personas: list[Persona], price: float) -> None:
    valid = {"too_cheap": 1.0, "cheap": 2.0, "expensive": 3.0, "too_expensive": 4.0}
    fake = _Fake([{**valid, "too_expensive": price}, valid])
    panel = select_personas(personas, 2, seed=0)
    answers = asyncio.run(survey_panel(fake, panel, Image.new("RGB", (32, 32)), ["price_vw"], 1))

    assert len(answers) == 2 and fake.calls == 2
    assert answers[0].respondent == panel[0].id and answers[0].error
    assert answers[0].too_cheap is None and answers[0].too_expensive is None
    assert answers[1].respondent == panel[1].id and not answers[1].error
    assert answers[1].too_cheap == 100 and answers[1].too_expensive == 400


def _arm(name: str, rpv: float, diff: float | None = None, lo: float = 0.0, hi: float = 0.0, units: tuple[float, float, float] | None = None):
    from store_emulator.domain.analysis import MetricComparison
    from store_emulator.domain.marketing import FocusOutcome, VariantResult
    vs = [] if diff is None else [MetricComparison(metric="spend", mean_a=700, mean_b=700 + diff, diff=diff, rel_diff=diff / 700,
                                                     ci_low=lo, ci_high=hi, prob_b_greater=0.9, sd_paired_diff=50, n_for_5pct_effect=1200)]
    focus = [] if units is None else [FocusOutcome(sku="A1", name="Cola", metric="units", control=0.1, variant=0.1 + units[0],
                                                   diff=units[0], rel_diff=units[0] / 0.1, ci_low=units[1], ci_high=units[2], prob_better=0.99)]
    return VariantResult(name=name, revenue_per_visitor=rpv, vs_control=vs, focus=focus)


def _report(variants, winner: str = ""):
    from store_emulator.domain.marketing import ExperimentReport
    return ExperimentReport(experiment_id="exp_1", name="Cola test", setup_id="s1", engine="rule", panel_size=300, currency="USD",
                            visitors_per_day=500, focus_skus=["A1"], control=_arm("Control", 700), variants=variants, winner=winner)


def test_report_recommends_the_winner_and_flags_losers() -> None:
    from store_emulator.engine.marketing.report import findings, money, report_html, report_markdown
    r = _report([_arm("Sign", 720, 20, 5, 35), _arm("Bottom shelf", 680, -20, -35, -6)], winner="Sign")
    f = findings(r)
    assert "Sign earns +$0.20 per visitor" in f.headline
    assert any("Roll out Sign" in x and "+$100.00 a day" in x for x in f.recommendation)
    assert any(x.startswith("Avoid Bottom shelf") for x in f.recommendation)
    html = report_html(r, "Layout 1")
    assert "Layout 1" in html and html.count("<svg") == 1 and "clearly down" in html
    assert "| A · Control |" in report_markdown(r)
    assert money(-1234, "USD", signed=True) == "−$12.34" and money(1500, "KRW") == "₩1,500"


def test_report_without_a_winner_explains_product_only_lifts_and_sample_size() -> None:
    from store_emulator.engine.marketing.report import findings
    f = findings(_report([_arm("-20 %", 702, 2, -8, 12, units=(0.05, 0.02, 0.08))]))
    assert f.headline.startswith("No variant changes revenue")
    assert any("sells more of the tracked product" in x for x in f.recommendation)
    assert any("about 1,200 shoppers per arm" in x for x in f.recommendation)


def test_price_sweep_gives_a_demand_curve(store: Store, personas: list[Persona]) -> None:
    from store_emulator.application.presets.behavior import BEHAVIOR_PATTERNS, sample_cue
    from store_emulator.engine.marketing import price_response
    from store_emulator.engine.marketing.report import report_html

    panel = select_personas(personas, 200, seed=4)
    evaluator = LayoutEvaluator(SimulationConfig(seed=4), panel, sample_cue, BEHAVIOR_PATTERNS, AStarPathFinder(),
                                OptimizeObjective.REVENUE_PER_VISITOR)
    arms = []
    for name, price in (("Cheaper", 89), ("Dearer", 189), ("Much dearer", 259)):
        v, applied, warnings = apply_changes(store, [VariantChange(kind="price", sku="A0017", price=price, keep_reference=True)])
        arms.append((name, v, applied, warnings))
    control, results, _ = asyncio.run(run_experiment(evaluator, store, arms, panel, ["A0017"]))
    assert control.prices == {"A0017": 129} and [r.prices["A0017"] for r in results] == [89, 189, 259]
    pr = price_response(control, results, {name: [VariantChange(kind="price", sku="A0017", price=p, keep_reference=True)]
                                           for name, p in (("Cheaper", 89), ("Dearer", 189), ("Much dearer", 259))})
    assert pr is not None and [p.price for p in pr.points] == [89, 129, 189, 259]
    assert all(p.units_low <= p.units <= p.units_high for p in pr.points)
    assert pr.best_price in {89, 129, 189, 259}
    assert pr.elasticity is not None and pr.elasticity < 0        # dearer -> fewer units against the remembered price
    cut = next(i for r in v.racks for sl in r.slots for i in sl.items if i.sku == "A0017")
    assert cut.price == 259 and cut.regular_price == 129
    from store_emulator.domain.marketing import ExperimentReport
    rep = ExperimentReport(experiment_id="e", name="Sweep", setup_id="s", engine="rule", panel_size=200, currency="USD",
                           visitors_per_day=400, focus_skus=["A0017"], control=control, variants=results, price_response=pr)
    assert "Price response" in report_html(rep)


def test_shelf_comparison_is_paired_by_respondent() -> None:
    from store_emulator.domain.marketing import ShelfChoice
    from store_emulator.engine.marketing.shelf_test import compare_shelves, pick_shares

    def c(r: str, arm: str, pick: str, noticed: list[str]) -> ShelfChoice:
        return ShelfChoice(respondent=r, age_group="30s", gender="Female", arm=arm, pick_sku=pick, noticed=noticed)  # type: ignore[arg-type]

    choices = []
    for i in range(20):
        choices.append(c(f"p{i}", "control", "T" if i < 4 else "X", ["X", "T"] if i < 8 else ["X"]))
        choices.append(c(f"p{i}", "test", "T" if i < 12 else "X", ["T"] if i < 16 else ["X"]))
    choices.append(c("lonely", "test", "T", ["T"]))          # no control answer: left out of the pairs
    pick, noticed, first = compare_shelves(choices, "T")
    assert (pick.control, pick.test, pick.diff) == (0.2, 0.6, 0.4) and pick.ci_low > 0 and pick.prob_better > 0.99
    assert (noticed.control, noticed.test) == (0.4, 0.8) and (first.control, first.test) == (0.0, 0.8)
    shares = {s.sku: s for s in pick_shares(choices, {"T": "Target", "X": "Rival"})}
    assert shares["T"].name == "Target" and abs(shares["T"].control + shares["X"].control - 1) < 1e-9


def _priced(name: str, price: int, units: float, spend: float):
    from store_emulator.domain.marketing import FocusOutcome, VariantResult
    focus = [FocusOutcome(sku="A1", name="Cola", metric=m, control=c, variant=v, diff=v - c, rel_diff=(v - c) / c,
                          ci_low=v - c - 0.01, ci_high=v - c + 0.01, prob_better=0.5)
             for m, c, v in (("units", 0.10, units), ("spend", 25.0, spend))]
    return VariantResult(name=name, prices={"A1": price}, focus=focus)


def test_price_curve_uses_only_arms_that_change_the_products_price_alone() -> None:
    from store_emulator.engine.marketing import price_response

    control = _priced("Control", 249, 0.10, 25.0)
    arms = [_priced("Cut", 199, 0.13, 25.9), _priced("Cut + sign", 199, 0.30, 59.7), _priced("Rise", 299, 0.08, 23.9),
            _priced("Drinks -10 %", 224, 0.20, 44.8), _priced("Rise elsewhere", 349, 0.07, 24.4)]
    changes = {
        "Cut": [VariantChange(kind="discount", sku="A1", percent=-20)],
        "Cut + sign": [VariantChange(kind="discount", sku="A1", percent=-20), VariantChange(kind="promo", sku="A1", promo="SALE")],
        "Rise": [VariantChange(kind="price", sku="A1", price=299, keep_reference=True),
                 VariantChange(kind="promo", sku="B2", promo="NEW")],          # a sign on another product does not touch A1
        "Drinks -10 %": [VariantChange(kind="category_price", category="Drink", percent=-10)],
        "Rise elsewhere": [VariantChange(kind="price", sku="A1", price=349),
                           VariantChange(kind="move", sku="A1", rack_id="r1", level=3)],
    }
    pr = price_response(control, arms, changes)
    assert pr is not None and [p.arm for p in pr.points] == ["Cut", "Control", "Rise"]
    assert pr.best_price == 199   # not the sign arm's 199 with three times the units, nor the category arm
    # Two prices left once the sign and category arms are out: no curve at all.
    assert price_response(control, arms[1:2] + arms[3:], {k: v for k, v in changes.items() if k != "Rise"}) is None


def test_price_advice_states_the_elasticity_only_where_it_agrees_with_the_best_price() -> None:
    from store_emulator.domain.marketing import PricePoint, PriceResponse
    from store_emulator.engine.marketing.report import findings

    def advice(elasticity: float, best: int) -> str:
        points = [PricePoint(arm=a, price=p, units=0.1, units_low=0.1, units_high=0.1, revenue=r)
                  for a, p, r in (("Cut", 199, 30.0), ("Control", 249, 25.0), ("Rise", 299, 28.0))]
        r = _report([_arm("Cut", 700, 0, -5, 5)])
        r.price_response = PriceResponse(sku="A1", name="Cola", points=points, elasticity=elasticity, best_price=best)
        return next(x for x in findings(r).recommendation if x.startswith("Of the prices tested"))

    assert "$1.99 brings the most" in advice(-1.6, 199) and "elastic: a price cut grows" in advice(-1.6, 199)
    assert "inelastic: a price rise grows" in advice(-0.4, 299)
    # The curve's slope says "cut" but the highest price earned most (or the other way round): no contradictory advice.
    for e, best in ((-1.6, 299), (-0.4, 199), (0.3, 299)):
        text = advice(e, best)
        assert "a price cut grows" not in text and "a price rise grows" not in text and "within noise" in text


def test_concept_test_summary_calls_ties_and_overlaps_level() -> None:
    from store_emulator.domain.marketing import ScaleSummary, SurveyReport
    from store_emulator.engine.marketing.report import survey_report_html

    def leads(a: tuple[float, float, float], b: tuple[float, float, float]) -> str:
        scales = [ScaleSummary(question="appeal", stimulus=i, n=40, mean=m, ci_low=lo, ci_high=hi, top2=0.3,
                               distribution=[0, 10, 20, 10, 0]) for i, (m, lo, hi) in enumerate((a, b))]
        r = SurveyReport(survey_id="srv_1", name="Packs", model="fake", stimuli=["a", "b"], stimulus_names=["Leafy", "Clara"],
                         questions=["appeal"], currency="USD", respondents=40, errors=0, scales=scales)
        return survey_report_html(r)

    tie = leads((3.0, 2.8, 3.2), (3.0, 2.8, 3.2))
    assert "Leafy and Clara are level on pack appeal (3.00 out of 5)" in tie and "leads" not in tie
    overlap = leads((3.3, 3.0, 3.6), (3.1, 2.8, 3.4))
    assert "No clear leader on pack appeal: Leafy 3.30 vs 3.10 out of 5, intervals overlap." in overlap and "leads" not in overlap
    assert "Leafy leads on pack appeal (3.90 vs 3.10 out of 5)." in leads((3.9, 3.7, 4.1), (3.1, 2.8, 3.4))
