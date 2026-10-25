"""Campaigns for the same product retain separate impressions, clicks and costs."""

import asyncio

import pytest

from store_emulator.domain.online import ActionKind, BrowserState, PageKind, PageRef
from store_emulator.engine.online.ads import ad_rows
from store_emulator.engine.online.browser import build_page, numbering
from store_emulator.engine.online.policies import ModelPolicy
from store_emulator.engine.online.render import render_page
from store_emulator.engine.online.session import run_session
from tests.engine.test_online_ads import _ad, _site
from tests.engine.test_online_store import _FakeModel, _shoppers


@pytest.mark.parametrize("placement", ["home_tile", "sponsored_listing", "product_page"])
@pytest.mark.parametrize("quick_add", [False, True])
def test_each_tile_keeps_its_campaign_even_when_products_repeat(placement, quick_add):
    site = _site(_ad(placement, id="first"), _ad(placement, id="paused", active=False),
                 _ad(placement, id="second"), _ad(placement, product="missing", id="missing"),
                 _ad(placement, product="p011", id="third"), quick_add=quick_add)
    product = site.product("p010")
    assert product is not None
    product.stock = None
    state = BrowserState()
    if placement == "sponsored_listing":
        state.at = PageRef(page=PageKind.CATEGORY, category_id=product.category_id)
    elif placement == "product_page":
        state.at = PageRef(page=PageKind.PRODUCT, product_id="p001")
    page = build_page(site, state)
    cards = [c for g in page.grids for c in g.cards if c.open.action.ad_id]
    assert [(c.product.id, c.open.action.ad_id) for c in cards] == [
        ("p010", "first"), ("p010", "second"), ("p011", "third")]
    assert page.ads_shown == ["first", "second", "third"]
    for card in cards:
        if card.quick_add is not None:
            assert card.quick_add.action.ad_id == card.open.action.ad_id
    shot = render_page(page, site, numbering(page, 21))
    assert len({shot.boxes[c.open.index] for c in cards}) == 3


@pytest.mark.parametrize("vision", [False, True])
@pytest.mark.parametrize("pricing", ["cpc", "cpm"])
@pytest.mark.parametrize("quick_add", [False, True])
def test_model_click_and_report_charge_the_selected_campaign(vision, pricing, quick_add):
    site = _site(_ad("home_tile", id="first", pricing=pricing, cost=1000),
                 _ad("home_tile", id="second", pricing=pricing, cost=9000), quick_add=quick_add)
    product = site.product("p010")
    assert product is not None
    product.stock = None
    wanted = f"Add to cart: {product.name}" if quick_add else "Ad · Open product:"
    model = _FakeModel(want=wanted)
    session = asyncio.run(run_session(site, _shoppers(site, 1)[0], ModelPolicy(model, vision=vision),
                                      seed=19, max_steps=1, render=vision, shuffle_marks=False))
    step = session.steps[0]
    assert step.source == "model" and step.ads == ["first", "second"]
    assert step.choice is not None and step.choice.ad_id == "first"
    assert step.choice.kind == (ActionKind.ADD_TO_CART if quick_add else ActionKind.OPEN_PRODUCT)
    first, second = ad_rows(site, [session])
    assert first.impressions == second.impressions == first.reach == second.reach == 1
    assert first.clicks == 1 and second.clicks == 0
    assert first.cost == (1000 if pricing == "cpc" else 1)
    assert second.cost == (0 if pricing == "cpc" else 9)
