"""The shared online report calls a run like the in-app report: a variant that clearly converts better wins (the
largest gain), the control holds when every variant clearly converts worse, otherwise it is too close to call."""

from store_emulator.domain.online import OnlineRunResult, PairedDelta, VariantComparison, VariantSummary
from store_emulator.engine.online.report import verdict


def _store(name: str, conversion: float) -> VariantSummary:
    return VariantSummary(site_id=name, site_name=name, sessions=100, purchases=round(conversion * 100), conversion=conversion,
                          revenue=0, aov=0, revenue_per_session=0, bounce_rate=0, cart_abandonment=0, add_to_cart_rate=0,
                          avg_steps=0, avg_seconds=0, search_share=0, zero_result_searches=0, outcomes={}, actions={},
                          funnel=[], exits=[], segments=[], products=[], searches=[], clicks=[])


def _compare(name: str, diff: float, low: float, high: float) -> VariantComparison:
    return VariantComparison(site_id=name, site_name=name, deltas=[
        PairedDelta(metric="conversion", control=0.3, variant=0.3 + diff, diff=diff, ci_low=low, ci_high=high, n=100)])


def _run(*comparisons: VariantComparison) -> OnlineRunResult:
    stores = [_store("Control", 0.3), *(_store(c.site_name, 0.3) for c in comparisons)]
    return OnlineRunResult(run_id="r", policy="rule", currency="USD", variants=stores, comparisons=list(comparisons), shoppers=[])


def test_the_clearest_largest_gain_wins() -> None:
    tone, headline = verdict(_run(_compare("B", 0.05, 0.01, 0.09), _compare("C", 0.12, 0.04, 0.2), _compare("D", 0.3, -0.1, 0.7)))
    assert tone == "win" and headline.startswith("C wins") and "+12.0 points" in headline


def test_the_control_holds_only_when_every_variant_is_clearly_worse() -> None:
    assert verdict(_run(_compare("B", -0.1, -0.2, -0.01), _compare("C", -0.2, -0.3, -0.1)))[0] == "holds"
    assert verdict(_run(_compare("B", -0.1, -0.2, -0.01), _compare("C", -0.2, -0.3, 0.05)))[0] == "close"


def test_a_single_store_reads_its_orders() -> None:
    tone, headline = verdict(_run())
    assert tone == "single" and headline == "Control: 30 of 100 visits ordered (30.0%)"
