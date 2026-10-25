"""A reminder discount must not hide a better coupon from the shopper."""

import asyncio
import random

import pytest

from store_emulator.domain.online import ActionKind, BrowserState, CartLine, PageKind, PageRef
from store_emulator.engine.online.browser import apply, build_page, cart_totals, numbering, outline
from store_emulator.engine.online.policies import Memory, ModelPolicy, StepView
from store_emulator.engine.online.render import render_page
from tests.engine.test_online_store import _FakeModel, _shoppers, _site


@pytest.mark.parametrize("page", ["cart", "one_page", "review"])
@pytest.mark.parametrize("coupon,reminder,applied,price,offered", [
    (20, 10, False, 999, True), (20, 10, True, 999, False),
    (10, 20, False, 999, False), (10, 10, False, 999, False),
    (0, 10, False, 999, False), (10, 0, False, 999, True),
    (10, 0, True, 1, False),
])
def test_only_an_unused_better_coupon_is_offered(page, coupon, reminder, applied, price, offered):
    site = _site(coupon_code="SAVE", coupon_percent=coupon, coupon_public=True,
                 checkout_flow="one_page" if page == "one_page" else "multi_step")
    product = site.products[0]
    product.price = price
    state = BrowserState(at=PageRef(page=PageKind.CART if page == "cart" else PageKind.CHECKOUT,
                                    checkout_step="review"), cart=[CartLine(product_id=product.id)],
                         reminder_percent=reminder, coupon_applied=applied)
    view = build_page(site, state)
    controls = [c for c in view.active if c.action.kind == ActionKind.APPLY_COUPON]
    assert bool(controls) is offered
    if offered:
        updated = apply(site, state, controls[0].action, query="SAVE")
        assert updated.coupon_applied
        assert cart_totals(site, updated.cart, updated, at_review=True).discount == round(price * coupon / 100)
        assert not any(c.action.kind == ActionKind.APPLY_COUPON for c in build_page(site, updated).active)
    assert state.coupon_applied is applied


@pytest.mark.parametrize("vision", [False, True])
def test_model_can_apply_the_better_coupon_after_a_reminder(vision):
    site = _site(coupon_code="SAVE", coupon_percent=20, coupon_public=True, checkout_flow="one_page")
    product = site.products[0]
    product.price, product.stock = 1000, None
    state = BrowserState(device="mobile", large_text=True, at=PageRef(page=PageKind.CART),
                         cart=[CartLine(product_id=product.id)], reminder_percent=10)
    page = build_page(site, state)
    numbers = numbering(page, 34)
    shot = render_page(page, site, numbers)
    view = StepView(page, state, numbers, outline(page, site), image_url=shot.data_url())
    choice = asyncio.run(ModelPolicy(_FakeModel(want="Apply a coupon"), vision=vision).choose(
        site, _shoppers(site, 1)[0], view, Memory(), random.Random(3)))
    assert choice.source == "model" and choice.control.action.kind == ActionKind.APPLY_COUPON
    assert shot.boxes[choice.control.index][3] <= shot.height
    updated = apply(site, state, choice.control.action, query="SAVE")
    assert cart_totals(site, updated.cart, updated, at_review=True).discount == 200
