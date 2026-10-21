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
    assert charm_price(274) == 299 and charm_price(299) == 299 and charm_price(1200, 1) == 1200


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
