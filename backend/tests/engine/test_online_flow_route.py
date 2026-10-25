"""Marginally popular links can combine into a journey nobody actually took."""

import pytest

from store_emulator.domain.online import BrowserState, PageKind, SessionResult, SessionStep
from store_emulator.engine.online.analysis import summarize
from tests.engine.test_online_store import _site


def visit(pages, outcome):
    return SessionResult(shopper_id="shopper", site_id="s1", outcome=outcome,
        steps=[SessionStep(index=i, url="/", page=PageKind(page), state=BrowserState(), options=1)
               for i, page in enumerate(pages)])


@pytest.mark.parametrize("reverse", [False, True])
def test_busiest_route_is_a_whole_observed_journey(reverse):
    sessions = ([visit(["home", "product", "cart"], "abandoned_cart")] * 4
                + [visit(["search", "product", "checkout"], "purchased")] * 3
                + [visit(["category", "product", "checkout"], "purchased")] * 3)
    if reverse:
        sessions.reverse()
    summary = summarize(_site(), {}, sessions)
    assert summary.model_dump().get("flow_route") == ["home", "product", "cart", "abandoned_cart"]
    assert sum(link.sessions for link in summary.flow if link.target is None) == 10


@pytest.mark.parametrize("pages,outcome,expected", [
    ([], "left", []),
    (["home"], "bounced", ["home", "bounced"]),
    (["home", "search", "product", "cart", "sign_in", "checkout", "checkout", "order_complete"],
     "purchased", ["home", "search", "product", "cart", "sign_in", "checkout", "purchased"]),
])
def test_route_uses_the_chart_horizon_and_real_outcome(pages, outcome, expected):
    summary = summarize(_site(), {}, [visit(pages, outcome)])
    assert summary.model_dump().get("flow_route") == expected
