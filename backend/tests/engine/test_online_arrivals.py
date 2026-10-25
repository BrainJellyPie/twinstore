"""Where visits come from: the page each one starts on, and how that shows in the results."""

import asyncio

from store_emulator.domain.online import ARRIVALS, OnlineShopper, OnlineSite, PageKind, SessionResult
from store_emulator.engine.online.analysis import summarize
from store_emulator.engine.online.catalog import build_site
from store_emulator.engine.online.policies import RulePolicy
from store_emulator.engine.online.prompt import user_prompt
from store_emulator.engine.online.session import run_session
from store_emulator.engine.online.shoppers import landing, sample_shoppers

_MIX = {"purchase": 1.0, "browse": 1.0, "replenish": 1.0, "deal_hunt": 1.0}


def _site() -> OnlineSite:
    site = build_site("beauty", site_id="arr")
    return site.model_copy(update={"options": site.options.model_copy(update={"welcome_popup": "none", "cookie_banner": False})})


def _sessions(site: OnlineSite, shoppers: list[OnlineShopper]) -> list[SessionResult]:
    async def go() -> list[SessionResult]:
        return [await run_session(site, s, RulePolicy(), seed=4, max_steps=30, render=False) for s in shoppers]
    return asyncio.run(go())


def test_sources_are_drawn_apart_from_everything_else() -> None:
    site = _site()
    direct = sample_shoppers(site, 80, seed=2, missions=_MIX, mobile_share=0.5)
    mixed = sample_shoppers(site, 80, seed=2, missions=_MIX, mobile_share=0.5, arrivals={a: 1.0 for a in ARRIVALS})
    assert {s.arrival for s in direct} == {"direct"} and {s.arrival for s in mixed} == set(ARRIVALS)
    assert [s.model_dump(exclude={"arrival"}) for s in direct] == [s.model_dump(exclude={"arrival"}) for s in mixed]
    assert {s.arrival for s in sample_shoppers(site, 10, seed=2, missions=_MIX, mobile_share=0.5,
                                               arrivals={"direct": 0.0, "email": 0.0})} == {"direct"}


def test_each_source_lands_on_its_page() -> None:
    site = _site()
    shopper = next(s for s in sample_shoppers(site, 40, seed=3, missions={"replenish": 1.0}, mobile_share=0.0)
                   if s.target_product)
    assert landing(site, shopper).page == PageKind.HOME
    found = landing(site, shopper.model_copy(update={"arrival": "search_engine"}))
    assert found.page == PageKind.PRODUCT and found.product_id == shopper.target_product
    popular = {p.id for p in sorted(site.products, key=lambda p: -p.weekly_sales)[:8]}
    assert landing(site, shopper.model_copy(update={"arrival": "social"})).product_id in popular
    assert landing(site, shopper.model_copy(update={"arrival": "email"})).page == PageKind.DEALS
    no_deals = site.model_copy(update={"products": [p.model_copy(update={"list_price": 0}) for p in site.products]})
    assert landing(no_deals, shopper.model_copy(update={"arrival": "email"})).page == PageKind.HOME
    prompt = user_prompt(site, shopper.model_copy(update={"arrival": "social"}), page_title="Home", options=[(1, "Leave")],
                         history=[], elapsed=0, load_seconds=1, cart=(0, 0, ()), outline=None)
    assert "They came from a social media post." in prompt


def test_search_visitors_start_on_a_product_and_are_reported_by_source() -> None:
    site = _site()
    shoppers = sample_shoppers(site, 120, seed=5, missions=_MIX, mobile_share=0.5,
                               arrivals={"direct": 1.0, "search_engine": 1.0})
    sessions = _sessions(site, shoppers)
    for shopper, session in zip(shoppers, sessions, strict=True):
        if shopper.arrival == "search_engine":
            assert session.steps[0].page == PageKind.PRODUCT and "product_view" in session.reached
            assert session.viewed_products[0] == session.steps[0].state.at.product_id
        else:
            assert session.steps[0].page == PageKind.HOME
    rows = {r.value: r for r in summarize(site, {s.id: s for s in shoppers}, sessions).segments if r.dimension == "arrival"}
    assert set(rows) == {"direct", "search_engine"} and sum(r.sessions for r in rows.values()) == 120
    for value, row in rows.items():
        group = [s for sh, s in zip(shoppers, sessions, strict=True) if sh.arrival == value]
        assert row.bounce_rate == round(sum(s.outcome == "bounced" for s in group) / len(group), 4)
    # Landing on the product they look for converts better than starting from the home page.
    assert rows["search_engine"].conversion > rows["direct"].conversion
