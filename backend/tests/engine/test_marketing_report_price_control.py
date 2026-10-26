"""The control row of a price response has no interval of its own: the arms' intervals are measured from it."""

from store_emulator.domain.marketing import ExperimentReport, PricePoint, PriceResponse, VariantResult
from store_emulator.engine.marketing.report import report_html, report_markdown


def _report() -> ExperimentReport:
    return ExperimentReport(
        experiment_id="exp_test", name="Ladder", setup_id="setup_test", engine="rule", panel_size=300,
        currency="USD", visitors_per_day=500,
        control=VariantResult(name="Control", revenue_per_visitor=700),
        variants=[VariantResult(name="-10 %", revenue_per_visitor=710)],
        price_response=PriceResponse(sku="A", name="Cola", best_price=224, points=[
            PricePoint(arm="-10 %", price=224, units=0.02, units_low=0.017, units_high=0.027, revenue=4.48),
            PricePoint(arm="Control", price=249, units=0.017, units_low=0.017, units_high=0.017, revenue=4.15),
        ]),
    )


def test_control_row_shows_no_interval():
    markdown = report_markdown(_report())
    assert "| -10 % | $2.24 | 2.0 [1.7, 2.7] |" in markdown
    assert "| Control | $2.49 | 1.7 | $4.15 |" in markdown
    html = report_html(_report())
    assert "[1.7, 2.7]" in html and "[1.7, 1.7]" not in html
