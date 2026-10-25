"""Sponsored cards share the page budget without dropping organic results."""

import pytest

from store_emulator.domain.online import ActionKind, AdCampaign, BrowserState, PageKind, PageRef
from store_emulator.engine.online.browser import apply, build_page, numbering
from store_emulator.engine.online.render import render_page
from tests.engine.test_online_store import _site


def _listing_site(count=49, **options):
    site = _site("grocery_delivery", products_per_page=24, grid_columns=2, quick_add=True,
                 cookie_banner=True, sponsored_slots=0, **options)
    site.products = site.products[:count]
    for product in site.products:
        product.category_id = site.categories[0].id
        product.tags.append("batchtest")
        product.list_price = product.price + 100
    site.ads = [AdCampaign(id=f"ad{i}", name=f"Campaign {i}", product_id=p.id, placement="sponsored_listing")
                for i, p in enumerate(site.products[:4])]
    return site


@pytest.mark.parametrize("device", ["desktop", "mobile"])
@pytest.mark.parametrize("large", [False, True])
@pytest.mark.parametrize("kind", [PageKind.CATEGORY, PageKind.SEARCH, PageKind.DEALS])
def test_full_sponsored_pages_keep_every_control_inside_the_screenshot(device, large, kind):
    site = _listing_site()
    state = BrowserState(device=device, large_text=large, notice="Added to cart.",
                         at=PageRef(page=kind, category_id=site.categories[0].id, query="batchtest"))
    seen = []
    for index in range(3):
        page = build_page(site, state)
        numbers = numbering(page, 71)
        shot = render_page(page, site, numbers)
        assert set(shot.boxes) == set(numbers)
        assert all(0 <= x1 < x2 <= shot.width and 0 <= y1 < y2 <= shot.height
                   for x1, y1, x2, y2 in shot.boxes.values())
        cards = [c for grid in page.grids for c in grid.cards]
        assert 0 < len(cards) <= site.options.products_per_page
        seen.extend(c.product.id for c in cards if not c.open.action.ad_id)
        assert page.ads_shown == (["ad0", "ad1", "ad2", "ad3"] if index == 0 else [])
        nxt = next((c for c in page.active if c.action.kind == ActionKind.NEXT_PAGE), None)
        if nxt is None:
            break
        before = state.at
        state = apply(site, state, nxt.action)
        previous = next(c for c in build_page(site, state).active if c.action.kind == ActionKind.PREVIOUS_PAGE)
        assert apply(site, state, previous.action).at == before
    assert len(seen) == len(set(seen)) == 49
    assert set(seen) == {p.id for p in site.products}


@pytest.mark.parametrize("per", [4, 24])
@pytest.mark.parametrize("count", [1, 4, 24, 25])
def test_small_pages_and_boundary_totals_never_skip_an_organic_product(per, count):
    site = _listing_site(count)
    site.options.products_per_page = per
    state = BrowserState(at=PageRef(page=PageKind.CATEGORY, category_id=site.categories[0].id))
    seen = []
    for _ in range(9):
        page = build_page(site, state)
        cards = [c for grid in page.grids for c in grid.cards]
        organic = [c.product.id for c in cards if not c.open.action.ad_id]
        assert organic and len(cards) <= per
        seen.extend(organic)
        nxt = next((c for c in page.active if c.action.kind == ActionKind.NEXT_PAGE), None)
        if nxt is None:
            break
        state = apply(site, state, nxt.action)
    assert seen == [p.id for p in site.products]


def test_only_matching_active_campaigns_take_listing_space():
    site = _listing_site(25)
    site.ads[0].active = False
    site.ads[1].product_id = "missing"
    site.ads[2].placement = "home_tile"
    state = BrowserState(at=PageRef(page=PageKind.CATEGORY, category_id=site.categories[0].id))
    page = build_page(site, state)
    assert page.ads_shown == ["ad3"]
    assert len(page.grids[-1].cards) == 23
    sort = next(c for c in page.active if c.action.kind == ActionKind.SORT and c.action.target == "price_desc")
    ordered = apply(site, state, sort.action)
    expected = sorted(site.products, key=lambda p: (-p.price, p.id))
    assert [c.product.id for c in build_page(site, ordered).grids[-1].cards] == [p.id for p in expected[:23]]
    empty = build_page(site, BrowserState(at=PageRef(page=PageKind.SEARCH, query="notfoundxyz")))
    assert not empty.ads_shown and not empty.grids[0].cards and "No products match" in empty.grids[0].note
