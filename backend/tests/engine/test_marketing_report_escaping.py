"""Report text must stay text in every HTML output context."""

from store_emulator.domain.analysis import MetricComparison
from store_emulator.domain.marketing import ExperimentReport, VariantResult
from store_emulator.engine.marketing.report import report_html


def test_report_currency_is_text_in_kpis_and_svg_labels():
    comparison = MetricComparison(metric="spend", mean_a=700, mean_b=720, diff=20, rel_diff=20 / 700,
                                  ci_low=5, ci_high=35, prob_b_greater=0.9, sd_paired_diff=50,
                                  n_for_5pct_effect=1200)
    report = ExperimentReport(
        experiment_id="exp_test", name="Test", setup_id="setup_test", engine="rule", panel_size=300,
        currency="<currency-marker>", visitors_per_day=500,
        control=VariantResult(name="Control", revenue_per_visitor=700),
        variants=[VariantResult(name="Variant", revenue_per_visitor=720, vs_control=[comparison])],
    )

    html = report_html(report)

    assert "<CURRENCY-MARKER>" not in html
    assert "&lt;CURRENCY-MARKER&gt;" in html
