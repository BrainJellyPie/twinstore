import pytest
from store_emulator.domain.analysis import MetricComparison
from store_emulator.domain.marketing import ExperimentReport, FocusOutcome, VariantResult
from store_emulator.engine.marketing.report import findings, report_html, report_markdown


def report(product_only=False, baseline=0):
    start = 100 if product_only else baseline
    gain = 0 if product_only else 100
    spend = MetricComparison(metric='spend', mean_a=start, mean_b=start+gain, diff=gain,
                             rel_diff=gain/start if start else 0, ci_low=gain-1, ci_high=gain+1,
                             prob_b_greater=0.5 if product_only else 1, sd_paired_diff=1,n_for_5pct_effect=0)
    units = MetricComparison(metric='units', mean_a=0, mean_b=1, diff=1, rel_diff=0,
                             ci_low=.9,ci_high=1.1,prob_b_greater=1,sd_paired_diff=.1,n_for_5pct_effect=0)
    focus = FocusOutcome(sku='tea',name='Tea',metric='units',control=0,variant=1,diff=1,rel_diff=0,
                         ci_low=.9,ci_high=1.1,prob_better=1)
    return ExperimentReport(experiment_id='exp_test',name='Tea experiment',setup_id='s',engine='rule',
        panel_size=100,currency='USD',visitors_per_day=100,focus_skus=['tea'],winner='' if product_only else 'Offer',
        control=VariantResult(name='Control',revenue_per_visitor=start),
        variants=[VariantResult(name='Offer',revenue_per_visitor=start+gain,units_per_visitor=1,
                                vs_control=[spend,units],focus=[focus])])

@pytest.mark.parametrize('render',[lambda r: findings(r).headline, report_markdown, report_html])
def test_zero_baseline_gain_is_not_reported_as_zero_percent(render):
    text=render(report())
    assert 'from zero' in text
    assert '+0.0 %' not in text


def test_new_product_sales_do_not_claim_zero_percent_growth():
    text=' '.join(findings(report(product_only=True)).recommendation)
    assert 'from zero' in text
    assert '+0 %' not in text


def test_positive_baseline_keeps_relative_revenue_gain():
    assert '+50.0 %' in findings(report(baseline=200)).headline
