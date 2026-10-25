"""Online carts and orders cannot exceed the displayed finite stock."""

import pytest

from store_emulator.domain.online import ActionKind, BrowserState, CartLine, OnlineAction, PageKind, PageRef
from store_emulator.engine.online.browser import apply, build_page, cart_totals
from tests.engine.test_online_store import _site


@pytest.mark.parametrize("stock", [0, 1, 2, 98, 99, 100, None])
@pytest.mark.parametrize("kind", [ActionKind.ADD_TO_CART, ActionKind.INCREASE_QUANTITY])
def test_repeated_actions_respect_stock_and_the_cart_quantity_limit(stock, kind):
    site = _site(welcome_popup="none", quick_add=True)
    product = site.products[0]
    product.stock = stock
    original = site.model_dump()
    state = BrowserState()
    for _ in range(102):
        previous = state.model_dump()
        next_state = apply(site, state, OnlineAction(kind=kind, target=product.id))
        assert state.model_dump() == previous
        state = next_state
    expected = 99 if stock is None else min(99, stock)
    assert sum(line.quantity for line in state.cart) == expected
    assert cart_totals(site, state.cart, state, at_review=True).subtotal == product.price * expected
    assert site.model_dump() == original


@pytest.mark.parametrize("stock", [1, 2, 99, None])
@pytest.mark.parametrize("page", [PageKind.PRODUCT, PageKind.CART, PageKind.CATEGORY, PageKind.WISHLIST])
def test_exhausted_products_do_not_offer_another_add_but_can_still_checkout(stock, page):
    site = _site(welcome_popup="none", quick_add=True, one_click_buy=True)
    product = site.products[0]
    product.stock = stock
    quantity = 99 if stock is None else stock
    state = BrowserState(at=PageRef(page=page, product_id=product.id, category_id=product.category_id),
                         cart=[CartLine(product_id=product.id, quantity=quantity)], wishlist=[product.id],
                         guest=True, address_added=True, payment_method="card")
    controls = build_page(site, state).active
    assert not any(c.action.target == product.id and c.action.kind in {
        ActionKind.ADD_TO_CART, ActionKind.INCREASE_QUANTITY} for c in controls)
    if page == PageKind.PRODUCT:
        buy = next(c for c in controls if c.action.kind == ActionKind.BUY_NOW)
        checked = apply(site, state, buy.action)
        assert checked.at.page == PageKind.CHECKOUT and checked.cart == state.cart
    removed = apply(site, state, OnlineAction(kind=ActionKind.REMOVE_FROM_CART, target=product.id))
    if page == PageKind.PRODUCT:
        assert any(c.action.kind == ActionKind.ADD_TO_CART for c in build_page(site, removed).active)


@pytest.mark.parametrize("problem", ["sold_out", "over_stock", "duplicate_rows", "unknown"])
def test_checkout_revalidates_stale_or_invalid_cart_rows(problem):
    site = _site(welcome_popup="none")
    product = site.products[0]
    product.stock = 1
    cart = [CartLine(product_id=product.id, quantity=2 if problem == "over_stock" else 1)]
    if problem == "sold_out": product.stock = 0
    elif problem == "duplicate_rows": cart.append(cart[0].model_copy())
    elif problem == "unknown": cart[0].product_id = "unknown"
    state = BrowserState(at=PageRef(page=PageKind.CHECKOUT, checkout_step="review"), cart=cart,
                         guest=True, address_added=True, payment_method="card")
    result = apply(site, state, OnlineAction(kind=ActionKind.PLACE_ORDER))
    assert not result.order_id and result.order == [] and result.order_total == 0
    assert result.cart == state.cart and result.notice


@pytest.mark.parametrize("stock,quantity", [(1, 1), (2, 2), (100, 99), (None, 99)])
def test_valid_stock_boundary_orders_keep_the_exact_units_and_price(stock, quantity):
    site = _site(welcome_popup="none")
    product = site.products[0]
    product.stock = stock
    state = BrowserState(cart=[CartLine(product_id=product.id, quantity=quantity)],
                         guest=True, address_added=True, payment_method="card")
    total = cart_totals(site, state.cart, state, at_review=True).total
    result = apply(site, state, OnlineAction(kind=ActionKind.PLACE_ORDER))
    assert result.order == state.cart and result.order_total == total and result.order_id
    assert result.cart == [] and result.at.page == PageKind.ORDER_COMPLETE
