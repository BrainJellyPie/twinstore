"""A rival's local IDs cannot change what a lost shopper was looking for."""

import asyncio

import pytest

from store_emulator.application import online
from store_emulator.domain.online import OnlineCategory, OnlineRunRequest
from store_emulator.engine.online.catalog import build_site
from store_emulator.engine.online.policies import Choice
from store_emulator.engine.online.shoppers import sample_shoppers


@pytest.mark.parametrize("search", ["off", "smart"])
@pytest.mark.parametrize("case", ["same", "unrelated_id", "moved_product", "renamed_sku", "missing_product",
                                  "category_id_collision", "moved_category", "category_empty_terms", "missing_category", "generic"])
def test_rival_visits_follow_product_and_category_identity(monkeypatch, search, case):
    source = build_site("toy_store", site_id="source")
    product = source.products[0].model_copy(update={"id": "p1", "name": "Jasmine Tea", "category_id": "c1",
                                                    "sku": "tea-sku", "description": "", "tags": []})
    source = source.model_copy(update={"categories": [OnlineCategory(id="c1", name="Tea")], "products": [product],
        "options": source.options.model_copy(update={"welcome_popup": "none", "cookie_banner": False, "search": search})})
    rival = source.model_copy(update={"id": "rival"})
    shopper = sample_shoppers(source, 1, seed=2, missions={"purchase": 1}, mobile_share=0)[0].model_copy(update={
        "target_product": "p1", "target_category": "c1", "target_terms": ["Jasmine Tea"], "goal": "Buy jasmine tea.",
    })
    expected_product, expected_category = "p1", "c1"
    unrelated = product.model_copy(update={"name": "Laptop", "sku": "computer-sku"})
    if case in {"unrelated_id", "category_id_collision"}:
        rival = rival.model_copy(update={"categories": [OnlineCategory(id="c1", name="Computers")], "products": [unrelated]})
        expected_product = None
    elif case == "moved_product":
        rival = rival.model_copy(update={"products": [unrelated, product.model_copy(update={"id": "other"})]})
        expected_product = "other"
    elif case == "renamed_sku":
        rival = rival.model_copy(update={"products": [unrelated, product.model_copy(update={"id": "other", "name": "House Brew"})]})
        expected_product = "other"
    elif case in {"missing_product", "missing_category"}:
        rival = rival.model_copy(update={"categories": [OnlineCategory(id="x", name="Computers")],
            "products": [unrelated.model_copy(update={"id": "other", "category_id": "x"})]})
        expected_product = None
    elif case in {"moved_category", "category_empty_terms"}:
        rival = rival.model_copy(update={"categories": [OnlineCategory(id="c1", name="Computers"), OnlineCategory(id="other", name="Tea")],
                                         "products": [product.model_copy(update={"category_id": "other"})]})
        expected_category = "other"
    if "category" in case:
        shopper = shopper.model_copy(update={"target_product": "", "target_terms": [] if case == "category_empty_terms" else ["Tea"],
                                             "mission": "compare"})
        if expected_product is not None:
            expected_product = ""
    if case == "generic":
        shopper = shopper.model_copy(update={"target_product": "", "target_category": "", "target_terms": [], "mission": "deal_hunt"})
        expected_product = expected_category = ""
    original = shopper.model_dump()
    seen = []

    class Policy:
        async def choose(self, site, visiting, view, memory, rng):
            if site.id == rival.id:
                seen.append(visiting)
            return Choice(view.page.leave)

    monkeypatch.setattr(online, "tries_rival", lambda *args: True)
    request = OnlineRunRequest(site_ids=[source.id], rival_site_id=rival.id, shoppers=1, max_steps=3, exit_survey=False)
    variants, visits = asyncio.run(online._simulate([source], [shopper], Policy(), request, lambda _: None, lambda _: None, rival))
    if expected_product is None:
        assert not seen and not visits and variants[0][0].rival is None
    else:
        assert len(seen) == len(visits) == 1
        assert seen[0].target_product == expected_product and seen[0].target_category == expected_category
        assert seen[0].arrival == "search_engine" and seen[0].goal == shopper.goal
        assert variants[0][0].rival is not None
    assert shopper.model_dump() == original
