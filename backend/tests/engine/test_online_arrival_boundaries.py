"""External search follows intent independently of the store's search setting."""
import asyncio
import random

import pytest

from store_emulator.engine.online.browser import search_products
from store_emulator.engine.online.policies import Choice, Memory, StepView
from store_emulator.engine.online.session import run_session
from store_emulator.engine.online.shoppers import landing, sample_shoppers
from tests.engine.test_online_arrivals import _site


@pytest.mark.parametrize("mode", ["off", "exact", "smart"])
@pytest.mark.parametrize("name,terms", [
    ("Unscented Face Cream", "FACE cream"), ("무향 얼굴 크림", "얼굴 크림"),
    ("无香面部乳霜", "无香面部乳霜"), ("無香料フェイスクリーム", "無香料フェイスクリーム"),
    ("Crema facial sin perfume", "crema facial"), ("Crème visage sans parfum", "crème visage"),
])
def test_external_search_follows_terms_even_when_shop_search_is_off(mode, name, terms):
    site = _site()
    other = site.products[0].model_copy(update={"id": "unrelated", "name": "Popular Soap", "tags": [], "weekly_sales": 900})
    wanted = other.model_copy(update={"id": "wanted", "name": name, "weekly_sales": 1})
    site = site.model_copy(update={"products": [other, wanted], "options": site.options.model_copy(update={"search": mode})})
    shopper = sample_shoppers(site, 1, seed=4, missions={"purchase": 1.0}, mobile_share=0)[0].model_copy(update={
        "arrival": "search_engine", "target_category": wanted.category_id, "target_terms": [terms], "target_product": "",
    })
    assert landing(site, shopper).product_id == wanted.id
    if mode == "off":
        assert search_products(site, terms) == []
    assert site.options.search == mode


@pytest.mark.parametrize("target,terms,category,expected", [
    ("first", ["Specific Serum"], "missing", "first"),
    ("missing", ["Specific Serum"], "missing", "second"),
    ("", ["nonexistent"], "missing", "first"),
    ("", [], "missing", "first"),
])
def test_search_keeps_explicit_products_and_deterministic_fallbacks(target, terms, category, expected):
    site = _site()
    first = site.products[0].model_copy(update={"id": "first", "name": "Popular Soap", "tags": [], "weekly_sales": 900})
    second = first.model_copy(update={"id": "second", "name": "Specific Serum", "weekly_sales": 1, "stock": 0})
    site = site.model_copy(update={"products": [first, second]})
    shopper = sample_shoppers(site, 1, seed=4, missions={"purchase": 1.0}, mobile_share=0)[0].model_copy(update={
        "arrival": "search_engine", "target_category": category, "target_terms": terms, "target_product": target,
    })
    assert landing(site, shopper).product_id == expected


@pytest.mark.parametrize("arrival,expected_views", [("direct", 0), ("email", 0), ("search_engine", 1), ("social", 1)])
def test_landing_product_counts_toward_the_shoppers_comparison_goal(arrival, expected_views):
    site = _site()
    shopper = sample_shoppers(site, 1, seed=4, missions={"compare": 1.0}, mobile_share=0)[0].model_copy(update={"arrival": arrival})
    observed: list[int] = []

    class Observe:
        async def choose(self, site, shopper, view: StepView, memory: Memory, rng: random.Random) -> Choice:
            observed.append(memory.views)
            return Choice(view.page.leave)

    session = asyncio.run(run_session(site, shopper, Observe(), seed=4, max_steps=2, render=False))
    assert observed == [expected_views]
    assert len(session.viewed_products) == expected_views
    assert ("product_view" in session.reached) == bool(expected_views)
