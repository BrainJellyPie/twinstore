"""Cart reminder email: who gets it, who comes back to the saved cart, and what the store recovers."""

import asyncio

from store_emulator.domain.online import BrowserState, CartLine, OnlineShopper, OnlineSite, PageKind, PageRef, SessionResult
from store_emulator.engine.online.analysis import clickstream_csv, summarize
from store_emulator.engine.online.browser import build_page, cart_totals, outline, returning
from store_emulator.engine.online.catalog import build_site
from store_emulator.engine.online.policies import RulePolicy, comes_back
from store_emulator.engine.online.session import run_session
from store_emulator.engine.online.shoppers import sample_shoppers


def _site(**options: object) -> OnlineSite:
    site = build_site("electronics", site_id="rem")
    return site.model_copy(update={"options": site.options.model_copy(update={"welcome_popup": "none", **options})})


def _sessions(site: OnlineSite, shoppers: list[OnlineShopper]) -> list[SessionResult]:
    async def go() -> list[SessionResult]:
        return [await run_session(site, s, RulePolicy(), seed=8, max_steps=30, render=False) for s in shoppers]
    return asyncio.run(go())


def test_the_reminder_reaches_carts_left_behind_and_changes_nothing_else() -> None:
    control = _site(service_fee=900)
    variant = _site(service_fee=900, cart_reminder=True, cart_reminder_percent=20)
    shoppers = sample_shoppers(control, 220, seed=2, missions={"purchase": 1.0, "deal_hunt": 0.5}, mobile_share=0.5)
    base, test = _sessions(control, shoppers), _sessions(variant, shoppers)
    assert not any(s.reminded or s.returned_at is not None for s in base)
    assert summarize(control, {s.id: s for s in shoppers}, base).recovery is None
    for b, t in zip(base, test, strict=True):
        assert t.reminded == (b.outcome == "abandoned_cart")
        if t.returned_at is None:
            assert t.model_dump(exclude={"reminded"}) == b.model_dump(exclude={"reminded"})
            continue
        # The first visit is the same; the next one opens the saved cart with the email's discount.
        assert [st.model_dump() for st in t.steps[:t.returned_at]] == [st.model_dump() for st in b.steps]
        back = t.steps[t.returned_at]
        assert back.page == PageKind.CART and back.state.reminder_percent == 20
        assert back.state.cart == b.steps[-1].state.cart
        if t.outcome == "purchased":
            assert t.discount == round(t.subtotal * 20 / 100)
    returned = [t for t in test if t.returned_at is not None]
    won = [t for t in returned if t.outcome == "purchased"]
    assert returned and won
    row = summarize(variant, {s.id: s for s in shoppers}, test).recovery
    assert row is not None and (row.emails, row.returned, row.recovered) == (
        sum(t.reminded for t in test), len(returned), len(won))
    assert row.revenue == sum(t.order_total for t in won) and row.discount == sum(t.discount for t in won)
    header, *rows = clickstream_csv([(variant, test, {s.id: s for s in shoppers})]).splitlines()
    column = header.lstrip("\ufeff").split(",").index("visit")
    visits = [line.split(",")[column] for line in rows]
    assert set(visits) == {"1", "2"}


def test_a_discount_brings_more_price_sensitive_shoppers_back() -> None:
    shopper = sample_shoppers(_site(), 1, seed=1, missions={"purchase": 1.0}, mobile_share=0.0)[0]
    thrifty = shopper.model_copy(update={"price_sensitivity": 0.9})
    relaxed = shopper.model_copy(update={"price_sensitivity": 0.1})
    assert comes_back(thrifty, 0) == comes_back(relaxed, 0)
    assert comes_back(thrifty, 15) > comes_back(relaxed, 15) > comes_back(relaxed, 0)
    assert comes_back(thrifty, 50) <= 0.6


def test_the_better_of_a_coupon_and_the_reminder_discount_applies() -> None:
    site = _site(coupon_code="SAVE10", coupon_percent=10)
    product = next(p for p in site.products if p.stock != 0)
    cart = [CartLine(product_id=product.id, quantity=2)]
    reminded = returning(BrowserState(cart=cart), 15)
    assert reminded.at.page == PageKind.CART and "15% off" in reminded.notice
    assert cart_totals(site, cart, reminded, at_review=False).discount == round(product.price * 2 * 15 / 100)
    both = reminded.model_copy(update={"coupon_applied": True})
    assert cart_totals(site, cart, both, at_review=False).discount == round(product.price * 2 * 15 / 100)
    assert any("Welcome-back discount (15%)" in line for line in outline(build_page(site, both), site))
    coupon_wins = returning(BrowserState(cart=cart, coupon_applied=True), 5)
    assert cart_totals(site, cart, coupon_wins, at_review=False).discount == round(product.price * 2 * 10 / 100)
    assert any("Coupon SAVE10" in line for line in outline(build_page(site, coupon_wins), site))
    assert build_page(site, BrowserState(at=PageRef(page=PageKind.CART), cart=cart)).kind == PageKind.CART
