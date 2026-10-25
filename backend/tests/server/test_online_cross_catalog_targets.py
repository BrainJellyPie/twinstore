"""A paired shopper keeps their shopping intent across catalogs with local IDs."""

import asyncio
import random

import pytest

from store_emulator.application.online import _simulate
from store_emulator.domain.online import OnlineCategory, OnlineRunRequest, OnlineShopper
from store_emulator.engine.online.catalog import build_site
from store_emulator.engine.online.policies import Choice, Memory, StepView, relevance
from store_emulator.engine.online.shoppers import sample_shoppers


@pytest.mark.parametrize("arrival", ["direct", "search_engine"])
@pytest.mark.parametrize("case", ["same", "moved", "missing", "sku_renamed", "ambiguous", "renamed_category", "unrelated_category",
                                  "marker_collision", "different_sku"])
def test_targets_are_bound_to_the_matching_product_and_category(case, arrival):
    source = build_site("grocery_delivery", site_id="source")
    wanted = source.products[0].model_copy(update={"id": "p1", "name": "Milk 1L", "category_id": "c1", "sku": ""})
    source = source.model_copy(update={"categories": [OnlineCategory(id="c1", name="Dairy")], "products": [wanted],
                                        "options": source.options.model_copy(update={"welcome_popup": "none", "cookie_banner": False})})
    variant = source.model_copy(update={"id": "variant"})
    expected_product, expected_category = "p1", "c1"
    if case == "moved":
        variant = variant.model_copy(update={"categories": [OnlineCategory(id="different", name="Dairy")],
            "products": [wanted.model_copy(update={"id": "other_id", "category_id": "different"})]})
        expected_product, expected_category = "other_id", "different"
    elif case == "missing":
        variant = variant.model_copy(update={"products": [wanted.model_copy(update={"name": "Cheese"})]})
        expected_product = None
    elif case == "sku_renamed":
        wanted = wanted.model_copy(update={"sku": "milk-sku"})
        source = source.model_copy(update={"products": [wanted]})
        variant = variant.model_copy(update={"products": [wanted.model_copy(update={"id": "other_id", "name": "Our Milk"})]})
        expected_product = "other_id"
    elif case == "ambiguous":
        variant = variant.model_copy(update={"products": [wanted.model_copy(update={"id": "a"}), wanted.model_copy(update={"id": "b"})]})
        expected_product = None
    elif case == "renamed_category":
        variant = variant.model_copy(update={"categories": [OnlineCategory(id="c1", name="Electronics")],
                                               "products": [wanted.model_copy(update={"name": "Keyboard"})]})
        expected_product, expected_category = None, ""
    elif case == "unrelated_category":
        variant = variant.model_copy(update={"categories": [OnlineCategory(id="x", name="Other")],
                                               "products": [wanted.model_copy(update={"category_id": "x"})]})
        expected_product, expected_category = None, ""
    elif case == "marker_collision":
        variant = variant.model_copy(update={"products": [wanted.model_copy(update={"name": "Cheese"}),
                                                         wanted.model_copy(update={"id": "missing:p1", "name": "Butter"})]})
        expected_product = None
    elif case == "different_sku":
        source = source.model_copy(update={"products": [wanted.model_copy(update={"sku": "wanted-sku"})]})
        variant = variant.model_copy(update={"products": [wanted.model_copy(update={"sku": "other-sku"})]})
        expected_product = None
    shopper = sample_shoppers(source, 1, seed=7, missions={"replenish": 1}, mobile_share=0)[0].model_copy(update={"arrival": arrival})
    original = shopper.model_dump()
    seen: dict[str, OnlineShopper] = {}

    class Capture:
        async def choose(self, site, shopper, view: StepView, memory: Memory, rng: random.Random) -> Choice:
            seen[site.id] = shopper
            if site.id == variant.id and arrival == "search_engine" and expected_product is not None:
                assert view.state.at.product_id == expected_product
            return Choice(view.page.leave)

    request = OnlineRunRequest(site_ids=[source.id, variant.id], shoppers=1, max_steps=3, exit_survey=False)
    asyncio.run(_simulate([source, variant], [shopper], Capture(), request, lambda _: None, lambda _: None))
    bound = seen[variant.id]
    assert bound.target_category == expected_category
    if expected_product is None:
        assert bound.target_product and variant.product(bound.target_product) is None
        assert all(relevance(bound, p, variant) < 1 for p in variant.products)
    else:
        assert bound.target_product == expected_product
        assert relevance(bound, variant.product(expected_product), variant) == 1
    assert bound.model_dump(exclude={"target_product", "target_category"}) == shopper.model_dump(exclude={"target_product", "target_category"})
    assert shopper.model_dump() == original and seen[source.id] == shopper


def test_builtin_grocery_goal_does_not_become_an_electronics_product():
    source = build_site("grocery_delivery", site_id="a")
    variant = build_site("electronics", site_id="b")
    shopper = next(s for s in sample_shoppers(source, 100, seed=1, missions={"replenish": 1}, mobile_share=0)
                   if variant.product(s.target_product))
    seen: list[float] = []

    class Capture:
        async def choose(self, site, shopper, view: StepView, memory: Memory, rng: random.Random) -> Choice:
            if site.id == variant.id:
                seen.extend(relevance(shopper, p, site) for p in site.products)
            return Choice(view.page.leave)

    request = OnlineRunRequest(site_ids=[source.id, variant.id], shoppers=1, max_steps=3, exit_survey=False)
    asyncio.run(_simulate([source, variant], [shopper], Capture(), request, lambda _: None, lambda _: None))
    assert seen and max(seen) < 1
