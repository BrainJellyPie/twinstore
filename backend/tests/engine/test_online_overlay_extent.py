"""A short underlying page must not crop the menu or welcome dialog."""

import asyncio
import random

import pytest

from store_emulator.domain.online import ActionKind, BrowserState, PageKind, PageRef
from store_emulator.engine.online.browser import apply, build_page, numbering, outline
from store_emulator.engine.online.policies import Memory, ModelPolicy, StepView
from store_emulator.engine.online.render import render_page
from tests.engine.test_online_store import _FakeModel, _shoppers, _site


@pytest.mark.parametrize("kind", [PageKind.CART, PageKind.WISHLIST, PageKind.HELP, PageKind.SETTINGS, PageKind.SEARCH])
@pytest.mark.parametrize("device", ["desktop", "mobile"])
@pytest.mark.parametrize("large", [False, True])
def test_menu_controls_fit_even_when_the_underlying_page_is_short(kind, device, large):
    site = _site("grocery_delivery", cookie_banner=False)
    state = BrowserState(device=device, large_text=large, at=PageRef(page=kind, query="nothing-matches"), overlay="menu")
    original = state.model_dump()
    page = build_page(site, state)
    numbers = numbering(page, 21)
    shot = render_page(page, site, numbers)
    assert set(shot.boxes) == set(numbers)
    assert all(0 <= left < right <= shot.width and 0 <= top < bottom <= shot.height
               for left, top, right, bottom in shot.boxes.values())
    close = next(c for c in page.active if c.action.kind == ActionKind.CLOSE_MENU)
    assert apply(site, state, close.action).at == state.at
    assert apply(site, state, close.action).overlay == "none"
    assert state.model_dump() == original


@pytest.mark.parametrize("device", ["desktop", "mobile"])
@pytest.mark.parametrize("large", [False, True])
@pytest.mark.parametrize("popup", ["newsletter", "coupon"])
def test_welcome_dialog_fits_a_minimal_home_page(device, large, popup):
    site = _site(welcome_popup=popup, hero_banner=False, home_sections=[], cookie_banner=False)
    state = BrowserState(device=device, large_text=large, overlay="welcome")
    page = build_page(site, state)
    numbers = numbering(page, 45)
    shot = render_page(page, site, numbers)
    assert set(shot.boxes) == set(numbers)
    assert all(0 <= top < bottom <= shot.height for _, top, _, bottom in shot.boxes.values())
    assert {c.action.kind for c in page.active} == {
        ActionKind.CLOSE_POPUP, ActionKind.ACCEPT_POPUP, ActionKind.LEAVE,
    }


def test_vision_model_can_close_the_menu_from_an_empty_cart():
    site = _site("grocery_delivery", cookie_banner=False)
    state = BrowserState(device="mobile", large_text=True, at=PageRef(page=PageKind.CART), overlay="menu")
    page = build_page(site, state)
    numbers = numbering(page, 73)
    shot = render_page(page, site, numbers)
    model = _FakeModel(want="Close the menu")
    view = StepView(page, state, numbers, outline(page, site), image_url=shot.scaled_data_url(600))
    choice = asyncio.run(ModelPolicy(model, vision=True).choose(site, _shoppers(site, 1)[0], view,
                                                               Memory(), random.Random(8)))
    assert choice.source == "model" and choice.control.action.kind == ActionKind.CLOSE_MENU
    assert 0 < shot.boxes[choice.control.index][3] <= shot.height
    closed = apply(site, state, choice.control.action)
    assert closed.at.page == PageKind.CART and closed.overlay == "none"
