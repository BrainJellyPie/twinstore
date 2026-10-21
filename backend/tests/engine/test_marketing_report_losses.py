"""Report summaries must distinguish losses from uncertain changes and include the control."""

from store_emulator.domain.analysis import MetricComparison
from store_emulator.domain.marketing import ExperimentReport, VariantResult
from store_emulator.engine.marketing.report import findings, report_html


def losing_report():
    spend = MetricComparison(metric="spend", mean_a=700, mean_b=680, diff=-20, rel_diff=-20 / 700,
                             ci_low=-35, ci_high=-6, prob_b_greater=0.01, sd_paired_diff=50,
                             n_for_5pct_effect=1200)
    return ExperimentReport(experiment_id="exp_loss", name="Test", setup_id="setup_test", engine="rule",
                            panel_size=300, currency="USD", visitors_per_day=500,
                            control=VariantResult(name="Control", revenue_per_visitor=700),
                            variants=[VariantResult(name="Losing variant", revenue_per_visitor=680, vs_control=[spend])])


def test_a_clear_revenue_loss_is_not_described_as_no_change():
    finding = findings(losing_report())
    assert "No variant changes revenue" not in finding.headline
    assert "Losing variant" in finding.headline


def test_highest_observed_revenue_includes_the_control():
    html = report_html(losing_report())
    label = html.index("Highest")
    kpi = html[label:html.index("</div>", label)]
    assert "<b>Control</b>" in kpi
    assert "within noise" not in kpi
