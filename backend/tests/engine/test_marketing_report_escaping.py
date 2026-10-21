"""Report text must stay text in every HTML output context."""

import pytest

from store_emulator.domain.analysis import MetricComparison
from store_emulator.domain.marketing import ExperimentReport, PricePoint, PriceRange, PriceResponse, SurveyReport, VariantResult
from store_emulator.engine.marketing.report import report_html, survey_report_html


@pytest.mark.parametrize("with_price_response", [False, True])
def test_report_currency_is_text_in_kpis_and_svg_labels(with_price_response):
    comparison = MetricComparison(metric="spend", mean_a=700, mean_b=720, diff=20, rel_diff=20 / 700,
                                  ci_low=5, ci_high=35, prob_b_greater=0.9, sd_paired_diff=50,
                                  n_for_5pct_effect=1200)
    report = ExperimentReport(
        experiment_id="exp_test", name="Test", setup_id="setup_test", engine="rule", panel_size=300,
        currency="<currency-marker>", visitors_per_day=500,
        control=VariantResult(name="Control", revenue_per_visitor=700),
        variants=[VariantResult(name="Variant", revenue_per_visitor=720, vs_control=[comparison])],
    )
    if with_price_response:
        report.price_response = PriceResponse(
            sku="A", name="Product", best_price=200,
            points=[PricePoint(arm=str(price), price=price, units=0.2, units_low=0.1,
                               units_high=0.3, revenue=price * 0.2) for price in (100, 200, 300)],
        )

    html = report_html(report)

    assert "<CURRENCY-MARKER>" not in html
    assert "&lt;CURRENCY-MARKER&gt;" in html


def test_survey_currency_is_text_in_price_table_and_svg_labels():
    report = SurveyReport(
        survey_id="survey_test", name="Test", model="fake", stimuli=["product"], stimulus_names=["Product"],
        questions=["price_vw"], currency="<currency-marker>", respondents=5, errors=0,
        price=PriceRange(n=5, point_of_marginal_cheapness=100, optimal_price_point=200,
                         indifference_price_point=250, point_of_marginal_expensiveness=300,
                         curve=[(100, 1, 1, 0, 0), (300, 0, 0, 1, 1)]),
    )

    html = survey_report_html(report)

    assert "<CURRENCY-MARKER>" not in html
    assert "&lt;CURRENCY-MARKER&gt;" in html
