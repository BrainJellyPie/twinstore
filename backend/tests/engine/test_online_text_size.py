"""Visitor text-size choices override a site's default and survive navigation."""

import asyncio
import random

import pytest

from store_emulator.domain.online import ActionKind, BrowserState, PageKind, PageRef
from store_emulator.engine.online.browser import apply, build_page, initial_state, numbering, outline
from store_emulator.engine.online.policies import Memory, ModelPolicy, StepView
from tests.engine.test_online_store import _FakeModel, _shoppers, _site


@pytest.mark.parametrize("default_large", [False, True])
@pytest.mark.parametrize("device", ["desktop", "mobile"])
def test_repeated_toggles_change_the_actual_page_size_and_persist(default_large, device):
    site = _site("senior_care", large_text=default_large)
    state = initial_state(site, device=device).model_copy(update={"at": PageRef(page=PageKind.SETTINGS)})
    for expected in (not default_large, default_large, not default_large):
        page = build_page(site, state)
        toggle = next(c for c in page.active if c.action.kind == ActionKind.TOGGLE_LARGE_TEXT)
        assert toggle.action.label == ("Use large text" if expected else "Use normal text")
        old = state.model_dump()
        state = apply(site, state, toggle.action)
        assert old != state.model_dump()
        state = BrowserState.model_validate_json(state.model_dump_json())
        page = build_page(site, state)
        assert page.large_text is expected
        home = apply(site, state, page.header.home.action)
        assert build_page(site, home).large_text is expected
        back = build_page(site, home).back
        assert back is not None
        state = apply(site, home, back.action)
        assert build_page(site, state).large_text is expected
    assert site.options.large_text is default_large
    assert build_page(site, initial_state(site, device=device)).large_text is default_large


@pytest.mark.parametrize("default_large", [False, True])
@pytest.mark.parametrize("saved_large", [False, True])
def test_older_saved_states_keep_their_original_default_and_enlargement(default_large, saved_large):
    site = _site(large_text=default_large)
    state = BrowserState.model_validate({"large_text": saved_large, "at": {"page": "settings"}})
    page = build_page(site, state)
    assert page.large_text is (default_large or saved_large)
    toggle = next(c for c in page.active if c.action.kind == ActionKind.TOGGLE_LARGE_TEXT)
    changed = apply(site, state, toggle.action)
    assert build_page(site, changed).large_text is not page.large_text


def test_text_model_can_actually_disable_the_senior_template_large_text():
    site = _site("senior_care")
    state = BrowserState(at=PageRef(page=PageKind.SETTINGS))
    page = build_page(site, state)
    model = _FakeModel(want="Use normal text")
    view = StepView(page, state, numbering(page, 13), outline(page, site))
    choice = asyncio.run(ModelPolicy(model, vision=False).choose(site, _shoppers(site, 1)[0], view,
                                                                Memory(), random.Random(8)))
    assert choice.source == "model" and choice.control.action.kind == ActionKind.TOGGLE_LARGE_TEXT
    changed = build_page(site, apply(site, state, choice.control.action))
    assert not changed.large_text
    assert changed.panels[0].lines[0].text == "Text size: normal"
