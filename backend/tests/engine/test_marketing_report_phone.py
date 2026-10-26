"""Marketing reports stay readable on a phone."""

import re

from store_emulator.domain.analysis import MetricComparison
from store_emulator.domain.marketing import ExperimentReport, PricePoint, PriceResponse, VariantResult
from store_emulator.engine.marketing.report import report_html


def test_wide_charts_scroll_on_a_phone_instead_of_shrinking():
    comparison = MetricComparison(metric="spend", mean_a=700, mean_b=720, diff=20, rel_diff=20 / 700,
                                  ci_low=5, ci_high=35, prob_b_greater=0.9, sd_paired_diff=50,
                                  n_for_5pct_effect=1200)
    report = ExperimentReport(
        experiment_id="exp_test", name="Test", setup_id="setup_test", engine="rule", panel_size=300,
        currency="USD", visitors_per_day=500,
        control=VariantResult(name="Control", revenue_per_visitor=700),
        variants=[VariantResult(name="Variant", revenue_per_visitor=720, vs_control=[comparison])],
        price_response=PriceResponse(
            sku="A", name="Product", best_price=200,
            points=[PricePoint(arm=str(price), price=price, units=0.2, units_low=0.1,
                               units_high=0.3, revenue=price * 0.2) for price in (100, 200, 300)],
        ),
    )

    html = report_html(report)

    wide = re.findall(r'<svg viewBox="[^"]*" width="100%"', html)
    assert len(wide) >= 2
    assert html.count('<div class="chart"><svg viewBox') == len(wide)
    assert "@media (max-width:640px)" in html and ".chart svg{min-width:600px}" in html
