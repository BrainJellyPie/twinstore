"""Large carts keep every offered control visible without changing the order."""

import asyncio
import random

import pytest

from store_emulator.domain.online import ActionKind, BrowserState, CartLine, OnlineAction, PageKind, PageRef
from store_emulator.engine.online.browser import apply, build_page, cart_totals, numbering, outline
from store_emulator.engine.online.policies import Memory, ModelPolicy, StepView
from store_emulator.engine.online.render import render_page
from tests.engine.test_online_store import _FakeModel, _shoppers, _site


@pytest.mark.parametrize("device", ["desktop", "mobile"])
@pytest.mark.parametrize("large", [False, True])
@pytest.mark.parametrize("currency", ["USD", "KRW", "JPY"])
def test_large_cart_pages_keep_controls_visible_and_totals_complete(device, large, currency):
    site = _site("grocery_delivery", products_per_page=24, coupon_code="SAVE", coupon_percent=10,
                 service_fee=199, preselected_addon_percent=5)
    site.currency = currency
    for product in site.products[:64]:
        product.stock = None
        product.name = (product.name + " premium everyday family refill " * 6)[:120]
    state = BrowserState(device=device, large_text=large, at=PageRef(page=PageKind.CART),
                         cart=[CartLine(product_id=p.id) for p in site.products[:64]], coupon_applied=True,
                         guest=True, address_added=True, payment_method="card")
    original = state.model_dump()
    expected_total = cart_totals(site, state.cart, state, at_review=True).total
    seen, urls = [], []
    for _ in range(4):
        page = build_page(site, state)
        numbers = numbering(page, 47)
        shot = render_page(page, site, numbers)
        assert set(shot.boxes) == set(numbers)
        assert all(0 <= left < right <= shot.width and 0 <= top < bottom <= shot.height
                   for left, top, right, bottom in shot.boxes.values())
        removed = [c.action.target for c in page.active if c.action.kind == ActionKind.REMOVE_FROM_CART]
        assert 0 < len(removed) <= 24
        seen.extend(removed)
        urls.append(page.url)
        assert any(c.action.kind == ActionKind.CHECKOUT for c in page.active)
        assert cart_totals(site, state.cart, state, at_review=True).total == expected_total
        nxt = next((c for c in page.active if c.action.kind == ActionKind.NEXT_PAGE), None)
        if nxt is None:
            break
        previous = state.at
        state = apply(site, state, nxt.action)
        back = next(c for c in build_page(site, state).active if c.action.kind == ActionKind.PREVIOUS_PAGE)
        assert apply(site, state, back.action).at == previous
    assert seen == [line["product_id"] for line in original["cart"]]
    assert len(urls) == len(set(urls)) == 3
    assert state.cart == [CartLine.model_validate(line) for line in original["cart"]]
    ordered = apply(site, state, OnlineAction(kind=ActionKind.PLACE_ORDER))
    assert ordered.order == state.cart and ordered.order_total == expected_total and ordered.order_id


@pytest.mark.parametrize("per_page", [4, 24])
def test_removing_the_only_item_on_the_last_cart_page_returns_to_the_previous_page(per_page):
    site = _site(products_per_page=per_page)
    state = BrowserState(at=PageRef(page=PageKind.CART, page_index=1),
                         cart=[CartLine(product_id=p.id) for p in site.products[:per_page + 1]])
    page = build_page(site, state)
    remove = next(c for c in page.active if c.action.kind == ActionKind.REMOVE_FROM_CART
                  and c.action.target == state.cart[-1].product_id)
    updated = apply(site, state, remove.action)
    assert state.at.page_index == 1 and len(state.cart) == per_page + 1
    assert updated.at.page_index == 0 and len(updated.cart) == per_page
    assert not any(c.action.kind in {ActionKind.NEXT_PAGE, ActionKind.PREVIOUS_PAGE}
                   for c in build_page(site, updated).active)


@pytest.mark.parametrize("count", [0, 1, 24, 25])
def test_cart_page_boundaries_and_empty_state(count):
    site = _site(products_per_page=24)
    state = BrowserState(at=PageRef(page=PageKind.CART),
                         cart=[CartLine(product_id=p.id) for p in site.products[:count]])
    page = build_page(site, state)
    assert sum(c.action.kind == ActionKind.REMOVE_FROM_CART for c in page.active) == min(count, 24)
    assert any(c.action.kind == ActionKind.NEXT_PAGE for c in page.active) == (count > 24)
    assert any(c.action.kind == ActionKind.CHECKOUT for c in page.active) == (count > 0)
    if not count:
        assert page.panels[0].title == "Your cart is empty"


@pytest.mark.parametrize("vision", [False, True])
def test_model_can_checkout_from_the_second_cart_page_without_losing_hidden_items(vision):
    site = _site(products_per_page=24)
    state = BrowserState(device="mobile", large_text=True, at=PageRef(page=PageKind.CART, page_index=1),
                         cart=[CartLine(product_id=p.id) for p in site.products[:40]])
    page = build_page(site, state)
    numbers = numbering(page, 13)
    shot = render_page(page, site, numbers)
    model = _FakeModel(want="Proceed to checkout")
    view = StepView(page, state, numbers, outline(page, site), image_url=shot.data_url())
    choice = asyncio.run(ModelPolicy(model, vision=vision).choose(site, _shoppers(site, 1)[0], view,
                                                                Memory(), random.Random(3)))
    assert choice.source == "model" and choice.control.action.kind == ActionKind.CHECKOUT
    assert shot.boxes[choice.control.index][3] <= shot.height
    checked = apply(site, state, choice.control.action)
    assert checked.at.page in {PageKind.SIGN_IN, PageKind.CHECKOUT} and checked.cart == state.cart
