"""Merchandise effects must not classify checkout adjustments as other products."""

import pytest

from store_emulator.domain.online import OrderLine, SessionResult
from store_emulator.engine.online.ads import ad_lifts, ad_rows
from tests.engine.test_online_ads import _ad, _site


@pytest.mark.parametrize("paid,discount,addon", [(80, 20, 0), (110, 0, 0), (115, 0, 15), (0, 100, 0), (125, 0, 0)])
def test_promoted_only_orders_do_not_invent_revenue_for_other_products(paid, discount, addon):
    control, variant = _site(), _site(_ad("hero_banner"))
    item = OrderLine(product_id="p010", name="Promoted", category_id="c1", quantity=1, price=100)
    baseline = SessionResult(shopper_id="s1", site_id=control.id, outcome="purchased", steps=[],
                             order=[item], subtotal=100, order_total=100)
    changed = baseline.model_copy(update={"order_total": paid, "discount": discount, "addon_paid": addon})
    lift, = ad_lifts(control, [baseline], [], variant, [changed], ad_rows(variant, [changed]))
    assert lift.units_diff == 0
    assert lift.revenue_diff == paid - 100
    assert lift.other_revenue_diff == 0


@pytest.mark.parametrize("flipped", [False, True])
def test_other_product_changes_use_recorded_line_prices_and_quantities(flipped):
    control, variant = _site(), _site(_ad("hero_banner"))
    promoted = OrderLine(product_id="p010", name="Promoted", category_id="c1", quantity=1, price=100)
    other = OrderLine(product_id="p020", name="Other", category_id="c1", quantity=2, price=30)
    baseline = SessionResult(shopper_id="s1", site_id=control.id, outcome="purchased", steps=[],
                             order=[promoted, other], subtotal=160, order_total=170)
    # Two promoted items, three other items, a 20% order coupon and 5 shipping.
    changed = baseline.model_copy(update={"order": [promoted.model_copy(update={"quantity": 2}),
                                                       other.model_copy(update={"quantity": 3})],
                                          "subtotal": 290, "order_total": 237, "discount": 58})
    rows = ad_rows(variant, [changed])
    args = (variant, [changed], rows, control, [baseline], []) if flipped else (control, [baseline], [], variant, [changed], rows)
    lift, = ad_lifts(*args)
    assert lift.units_diff == 1
    assert lift.revenue_diff == 67
    assert lift.other_revenue_diff == 30


def test_free_and_empty_orders_do_not_turn_fees_into_product_revenue():
    control, variant = _site(), _site(_ad("hero_banner"))
    free = OrderLine(product_id="p020", name="Free", category_id="c1", quantity=3, price=0)
    left = SessionResult(shopper_id="s1", site_id=control.id, outcome="left", steps=[])
    bought = left.model_copy(update={"outcome": "purchased", "order": [free], "order_total": 10})
    lift, = ad_lifts(control, [left], [], variant, [bought], ad_rows(variant, [bought]))
    assert lift.other_revenue_diff == 0
    assert lift.revenue_diff == 10
