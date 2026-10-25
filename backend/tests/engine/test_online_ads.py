"""Ads on online stores: placements on the page, impressions and clicks, attribution and incrementality."""

import asyncio

from store_emulator.domain.online import (
    ActionKind,
    AdCampaign,
    BrowserState,
    OnlineAction,
    OnlineShopper,
    OnlineSite,
    PageKind,
    PageRef,
    SessionResult,
)
from store_emulator.engine.online.ads import ad_lifts, ad_rows
from store_emulator.engine.online.analysis import summarize
from store_emulator.engine.online.browser import apply, build_page, initial_state, numbering
from store_emulator.engine.online.catalog import build_site
from store_emulator.engine.online.policies import RulePolicy
from store_emulator.engine.online.render import render_page
from store_emulator.engine.online.session import run_session
from store_emulator.engine.online.shoppers import sample_shoppers


def _site(*ads: AdCampaign, **options: object) -> OnlineSite:
    site = build_site("fashion", site_id="ads")
    opts = site.options.model_copy(update={"welcome_popup": "none", "cookie_banner": False, **options})
    return site.model_copy(update={"ads": list(ads), "options": opts})


def _ad(placement: str, product: str = "p010", **kw: object) -> AdCampaign:
    return AdCampaign.model_validate({"id": f"ad_{placement}", "name": placement, "product_id": product,
                                      "placement": placement, "headline": "Fresh drop", **kw})


def _ad_controls(site: OnlineSite, state: BrowserState) -> list[OnlineAction]:
    return [c.action for c in build_page(site, state).active if c.action.ad_id]


def test_each_placement_shows_its_ad_and_marks_the_click() -> None:
    plain = _site()
    target = plain.product("p010")
    assert target is not None
    hero = _site(_ad("hero_banner"))
    page = build_page(hero, BrowserState())
    assert page.ads_shown == ["ad_hero_banner"] and page.banner is not None and page.banner.product is not None
    click = next(a for a in _ad_controls(hero, BrowserState()))
    assert click.kind == ActionKind.OPEN_PRODUCT and click.target == "p010" and click.label.startswith("Ad · ")
    assert build_page(plain, BrowserState()).ads_shown == []

    tile = _site(_ad("home_tile"))
    assert [a.target for a in _ad_controls(tile, BrowserState())] == ["p010"]

    listing = _site(_ad("sponsored_listing"))
    on_category = BrowserState(at=PageRef(page=PageKind.CATEGORY, category_id=target.category_id))
    assert build_page(listing, on_category).ads_shown == ["ad_sponsored_listing"]
    elsewhere = next(c.id for c in listing.categories if c.id != target.category_id)
    assert build_page(listing, BrowserState(at=PageRef(page=PageKind.CATEGORY, category_id=elsewhere))).ads_shown == []

    cross = _site(_ad("product_page"))
    other = next(p for p in cross.products if p.id != "p010")
    assert build_page(cross, BrowserState(at=PageRef(page=PageKind.PRODUCT, product_id=other.id))).ads_shown == ["ad_product_page"]
    assert build_page(cross, BrowserState(at=PageRef(page=PageKind.PRODUCT, product_id="p010"))).ads_shown == []

    upsell = _site(_ad("cart_upsell"))
    cart = BrowserState(at=PageRef(page=PageKind.CART), cart=[{"product_id": other.id, "quantity": 1}])  # type: ignore[list-item]
    add = next(a for a in _ad_controls(upsell, cart))
    assert add.kind == ActionKind.ADD_TO_CART and [line.product_id for line in apply(upsell, cart, add).cart] == [other.id, "p010"]

    popup = _site(_ad("popup"))
    landing = initial_state(popup)
    assert landing.overlay == "promo"
    assert {c.action.kind for c in build_page(popup, landing).active} == {ActionKind.OPEN_PRODUCT, ActionKind.CLOSE_POPUP, ActionKind.LEAVE}
    viewed = apply(popup, landing, next(a for a in _ad_controls(popup, landing)))
    assert viewed.at.page == PageKind.PRODUCT and viewed.overlay == "none"


def test_paused_ads_and_missing_products_show_nothing() -> None:
    assert build_page(_site(_ad("hero_banner", active=False)), BrowserState()).ads_shown == []
    assert build_page(_site(_ad("hero_banner", product="nope")), BrowserState()).ads_shown == []
    assert initial_state(_site(_ad("popup", active=False))).overlay == "none"


def test_ads_are_drawn_where_they_can_be_clicked() -> None:
    site = _site(_ad("hero_banner"), _ad("home_tile", product="p020"))
    page = build_page(site, BrowserState())
    shot = render_page(page, site, numbering(page))
    ad_indexes = {c.index for c in page.active if c.action.ad_id}
    assert ad_indexes and ad_indexes <= set(shot.boxes)


def _sessions(site: OnlineSite, shoppers: list[OnlineShopper]) -> list[SessionResult]:
    async def go() -> list[SessionResult]:
        return [await run_session(site, s, RulePolicy(), seed=3, max_steps=30, render=False) for s in shoppers]
    return asyncio.run(go())


def test_attribution_and_incrementality_on_the_same_shoppers() -> None:
    control = _site()
    product = control.product("p010")
    assert product is not None
    shoppers = sample_shoppers(control, 150, seed=4, missions={"browse": 1.0, "purchase": 1.0}, mobile_share=0.5)
    ads = (_ad("hero_banner", cost=40), _ad("popup", pricing="cpm", cost=9000))
    variant = _site(*ads)
    base, test = _sessions(control, shoppers), _sessions(variant, shoppers)
    rows = {r.ad_id: r for r in ad_rows(variant, test)}
    hero, popup = rows["ad_hero_banner"], rows["ad_popup"]
    assert popup.reach == popup.impressions == 150  # the promo opens over every landing page
    assert hero.impressions >= hero.reach > 0 and hero.clicks + popup.clicks > 0
    assert hero.cost == hero.clicks * 40 and popup.cost == round(popup.impressions * 9000 / 1000)
    assert 0 <= hero.ctr <= 1 and (hero.roas is None) == (hero.cost == 0)
    assert hero.click_conversions + hero.view_conversions <= hero.reach
    units = sum(line.quantity for s in test for line in s.order if line.product_id == "p010")
    assert hero.units_sold == units
    lifts = {lift.ad_id: lift for lift in ad_lifts(control, base, [], variant, test, list(rows.values()))}
    lift = lifts["ad_hero_banner"]
    assert lift.site_id == variant.id and lift.units_with == units and lift.units_diff == units - lift.units_without
    assert lift.revenue_diff == sum(s.order_total for s in test) - sum(s.order_total for s in base)
    assert lift.iroas == round(lift.revenue_diff / hero.cost, 2)
    # The other way round (the store without the ad as the variant), the ad's effect keeps its sign.
    flipped = {x.ad_id: x for x in ad_lifts(variant, test, list(rows.values()), control, base, [])}
    assert flipped["ad_hero_banner"] == lift
    # An ad running in both stores adds nothing between them.
    assert ad_lifts(variant, test, list(rows.values()), variant, test, list(rows.values())) == []
    summary = summarize(variant, {s.id: s for s in shoppers}, test)
    assert [r.ad_id for r in summary.ads] == ["ad_hero_banner", "ad_popup"]
    assert summarize(control, {s.id: s for s in shoppers}, base).ads == []
    paused = _site(*(ad.model_copy(update={"active": False}) for ad in ads))
    assert summarize(paused, {s.id: s for s in shoppers}, base).ads == []


def test_a_popup_step_does_not_reshuffle_the_decisions_after_it() -> None:
    """Common random numbers are keyed to the decision point: shoppers who close the popup then decide the landing
    page exactly as in the store without it."""
    control = _site()
    shoppers = sample_shoppers(control, 60, seed=9, missions={"purchase": 1.0}, mobile_share=0.0)
    variant = _site(_ad("popup", product="p999"))  # promotes a product the store does not sell: no popup at all
    assert [s.model_dump() for s in _sessions(control, shoppers)] == [
        s.model_dump() for s in _sessions(variant, shoppers)]
    with_popup = _site(_ad("popup", product="p010"))
    base, test = _sessions(control, shoppers), _sessions(with_popup, shoppers)
    closed = [(b, t) for b, t in zip(base, test, strict=True)
              if t.steps[0].choice is not None and t.steps[0].choice.kind == ActionKind.CLOSE_POPUP]
    assert closed
    for b, t in closed:
        first, after = b.steps[0].choice, t.steps[1].choice
        assert first is not None and after is not None and (first.kind, first.target) == (after.kind, after.target)
