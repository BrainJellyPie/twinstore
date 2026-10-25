"""A vision shopper must see every offered wishlist control inside its screenshot."""

import pytest

from store_emulator.domain.online import ActionKind, BrowserState, PageKind, PageRef
from store_emulator.engine.online.browser import apply, build_page, numbering
from store_emulator.engine.online.render import render_page
from tests.engine.test_online_store import _site


@pytest.mark.parametrize("device", ["desktop", "mobile"])
@pytest.mark.parametrize("large", [False, True])
@pytest.mark.parametrize("per_page", [4, 24])
def test_wishlist_pages_show_every_saved_product_once_with_visible_controls(device, large, per_page):
    site = _site(quick_add=True, grid_columns=2, products_per_page=per_page, sponsored_slots=4)
    saved = [p.id for p in site.products[:36]]
    state = BrowserState(device=device, large_text=large, at=PageRef(page=PageKind.WISHLIST), wishlist=saved)
    original = state.model_dump()
    seen, urls = [], []
    for _ in range(10):
        page = build_page(site, state)
        shown = [card.product.id for grid in page.grids for card in grid.cards]
        assert 0 < len(shown) <= per_page
        seen.extend(shown)
        urls.append(page.url)
        numbers = numbering(page, 29)
        shot = render_page(page, site, numbers)
        assert set(shot.boxes) == set(numbers)
        assert all(0 <= left < right <= shot.width and 0 <= top < bottom <= shot.height
                   for left, top, right, bottom in shot.boxes.values())
        next_page = next((c for c in page.active if c.action.kind == ActionKind.NEXT_PAGE), None)
        if next_page is None:
            break
        previous = state
        state = apply(site, state, next_page.action)
        back = next(c for c in build_page(site, state).active if c.action.kind == ActionKind.PREVIOUS_PAGE)
        assert apply(site, state, back.action).at == previous.at
    assert seen == saved and len(set(urls)) == len(urls)
    assert original["wishlist"] == state.wishlist == saved
    last = build_page(site, state)
    product = next(c for c in last.active if c.action.kind == ActionKind.OPEN_PRODUCT)
    detail = apply(site, state, product.action)
    back = build_page(site, detail).back
    assert back is not None and apply(site, detail, back.action).at == state.at


@pytest.mark.parametrize("saved", [[], ["missing"], ["missing", "p001", "p002"]])
def test_empty_and_stale_wishlist_entries_keep_an_accurate_page(saved):
    site = _site(products_per_page=4)
    state = BrowserState(at=PageRef(page=PageKind.WISHLIST), wishlist=saved)
    page = build_page(site, state)
    expected = [pid for pid in saved if site.product(pid) is not None]
    assert [card.product.id for grid in page.grids for card in grid.cards] == expected
    assert not any(c.action.kind in {ActionKind.NEXT_PAGE, ActionKind.PREVIOUS_PAGE} for c in page.active)
    if not expected:
        assert page.grids[0].note == "Nothing saved yet."


def test_wishlist_sort_keeps_only_saved_products_and_starts_from_page_one():
    site = _site(products_per_page=4, sponsored_slots=4)
    saved = [p.id for p in site.products[:9]]
    state = BrowserState(at=PageRef(page=PageKind.WISHLIST, page_index=1), wishlist=saved)
    sort = next(c for c in build_page(site, state).active if c.action.kind == ActionKind.SORT and c.action.target == "price_asc")
    state = apply(site, state, sort.action)
    expected = sorted(site.products[:9], key=lambda p: (p.price, p.id))[:4]
    assert state.at.page_index == 0
    assert [card.product.id for grid in build_page(site, state).grids for card in grid.cards] == [p.id for p in expected]
