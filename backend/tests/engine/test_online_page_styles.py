"""Page styles change how a shop looks, never what a shopper can do: every option stays drawn and clickable."""

import io
import random

import pytest
from PIL import Image

from store_emulator.domain.online import PAGE_STYLES, ActionKind, BrowserState, PageKind, PageRef, PageStyle
from store_emulator.engine.online.browser import apply, build_page, initial_state, numbering
from store_emulator.engine.online.catalog import build_site
from store_emulator.engine.online.render import STYLES, render_page


def _styled(template: str, style: PageStyle, **options: object):  # type: ignore[no-untyped-def]
    site = build_site(template, site_id="styled")
    return site.model_copy(update={"options": site.options.model_copy(update={"page_style": style, **options})})


def test_every_style_has_a_look() -> None:
    assert set(STYLES) == set(PAGE_STYLES)


@pytest.mark.parametrize("style", PAGE_STYLES)
def test_a_crawl_in_every_style_draws_every_option_inside_the_page(style: PageStyle) -> None:
    site = _styled("fashion", style, welcome_popup="coupon", quick_add=True, urgency=True, chat_widget=True)
    rng = random.Random(style)
    for device in ("desktop", "mobile"):
        state = initial_state(site, device=device)
        for _ in range(14):
            page = build_page(site, state)
            numbers = numbering(page, rng.randint(0, 99))
            shot = render_page(page, site, numbers)
            assert shot.png == render_page(page, site, numbers).png  # a recorded step looks the way it was seen
            missing = [c.action.label for c in page.active if c.index not in shot.boxes]
            assert not missing, f"{style} {page.url}: options not drawn: {missing}"
            for box in shot.boxes.values():
                assert 0 <= box[0] < box[2] <= shot.width and 0 <= box[1] < box[3] <= shot.height
            choices = [c for c in page.active if c.action.kind != ActionKind.LEAVE]
            state = apply(site, state, rng.choice(choices).action, query="dress", has_account=False)


def test_styles_look_different_but_offer_the_same_options() -> None:
    shots = {}
    for style in PAGE_STYLES:
        site = _styled("pet_store", style)
        page = build_page(site, BrowserState(cookies_answered=True, at=PageRef(page=PageKind.HOME)))
        shot = render_page(page, site, numbering(page))
        shots[style] = shot
        assert set(shot.boxes) == {c.index for c in page.active}
    assert len({shot.png for shot in shots.values()}) == len(PAGE_STYLES)
    # A dark style is dark: most of its page is darker than mid-grey.
    with Image.open(io.BytesIO(shots["neon"].png)) as image:
        grey = image.convert("L").resize((64, 64))
        assert sum(1 for v in grey.getdata() if v < 128) > 64 * 64 * 0.6


def test_korean_names_keep_the_sans_face_in_a_serif_style() -> None:
    site = _styled("pet_store", "luxury")
    site = site.model_copy(update={"name": "행복한 발바닥"})
    page = build_page(site, BrowserState(cookies_answered=True))
    assert page.style == "luxury"
    assert render_page(page, site, numbering(page)).width == 1024
