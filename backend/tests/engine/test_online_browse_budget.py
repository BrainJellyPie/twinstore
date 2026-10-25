"""Browsing has no purchase plan; it still has the shopper's available budget."""

import pytest

from store_emulator.domain.online import SessionResult
from store_emulator.engine.online.catalog import build_site
from store_emulator.engine.online.interview import visit_text
from store_emulator.engine.online.prompt import user_prompt
from store_emulator.engine.online.shoppers import sample_shoppers


@pytest.mark.parametrize("mission", ["browse", "purchase"])
@pytest.mark.parametrize("currency,budget,expected", [
    ("USD", 100, "$1.00"), ("KRW", 1000, "1,000원"), ("USD", 0, "no fixed limit"),
])
def test_live_decision_and_post_visit_interview_keep_the_budget(mission, currency, budget, expected):
    site = build_site("fashion", site_id="web", currency=currency)
    shopper = sample_shoppers(site, 1, seed=4, missions={mission: 1}, mobile_share=0)[0].model_copy(update={"budget": budget})
    live = user_prompt(site, shopper, page_title="Checkout", options=[(1, "Close tab"), (2, "Place order")],
        history=[], elapsed=0, load_seconds=0, cart=(1, 1999, ("Shirt",)), outline=None)
    session = SessionResult(shopper_id=shopper.id, site_id=site.id, outcome="left", steps=[])
    replay = visit_text(site, shopper, session)
    assert f"Budget: {expected}." in live
    assert f"Budget: {expected}." in replay
    if mission == "browse":
        assert "No purchase planned." in live and "No purchase planned." in replay
