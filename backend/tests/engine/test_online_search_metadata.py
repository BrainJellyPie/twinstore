"""Smart search must find the category and tag terms given to online shoppers."""

import asyncio

import pytest

from store_emulator.domain.online import ActionKind, OnlineCategory, OnlineProduct
from store_emulator.engine.online.browser import search_products
from store_emulator.engine.online.catalog import build_site, template_ids
from store_emulator.engine.online.policies import ModelPolicy
from store_emulator.engine.online.session import run_session
from tests.engine.test_online_store import _FakeModel, _shoppers, _site


@pytest.mark.parametrize("template", template_ids())
def test_each_builtin_category_is_searchable_by_its_own_name(template):
    site = build_site(template, site_id="search")
    site.options.search = "smart"
    original = site.model_dump()
    for category in site.categories:
        expected = {p.id for p in site.products if p.category_id == category.id}
        assert expected <= {p.id for p in search_products(site, category.name)}, category.name
    assert site.model_dump() == original


@pytest.mark.parametrize("field", ["category", "tag"])
@pytest.mark.parametrize("words,query", [
    ("Apparel", "apparel"), ("Apparel", "  APPAREL  "), ("Apparel", "appa"),
    ("Soft fabric", "soft fabric"), ("Soft fabric", "soft"), ("Soft fabric", "soft unknown"),
    ("Soft fabric", "soft fabric unknown"), ("여름", "여름"), ("環境配慮", "環境配慮"),
])
def test_metadata_matches_have_the_same_word_coverage_as_name_matches(field, words, query):
    site = _site()
    site.categories = [OnlineCategory(id="c", name=words if field == "category" else "Unrelated")]
    site.products = [OnlineProduct(id="p", name="Cotton shirt", category_id="c", price=100,
                                  tags=[words] if field == "tag" else [])]
    assert [p.id for p in search_products(site, query)] == ["p"]


@pytest.mark.parametrize("query", ["soft absent missing", "absent", "", "  \u3000 ", "!!!", "so"])
def test_unknown_short_prefix_and_insufficient_word_coverage_do_not_match(query):
    site = _site()
    site.categories = [OnlineCategory(id="c", name="Unrelated")]
    site.products = [OnlineProduct(id="p", name="Cotton shirt", category_id="c", price=100, tags=["soft fabric"])]
    assert search_products(site, query) == []


@pytest.mark.parametrize("mode", ["smart", "exact", "off"])
def test_name_matches_still_rank_above_metadata_and_other_search_modes_keep_their_meaning(mode):
    site = _site(search=mode)
    site.categories = [OnlineCategory(id="c", name="Apparel"), OnlineCategory(id="other", name="Accessories")]
    site.products = [OnlineProduct(id="category", name="Cotton shirt", category_id="c", price=100),
                     OnlineProduct(id="tag", name="Wool scarf", category_id="other", price=200, tags=["apparel"]),
                     OnlineProduct(id="name", name="Apparel poster", category_id="other", price=300)]
    expected = {"smart": ["name", "category", "tag"], "exact": ["name"], "off": []}
    assert [p.id for p in search_products(site, "apparel")] == expected[mode]


@pytest.mark.parametrize("query", ["apparel", "footwear"])
def test_model_search_reaches_results_and_records_the_real_match_count(query):
    site = _site(welcome_popup="none")
    shopper = _shoppers(site, 1)[0]
    expected = sum(p.category_id == next(c.id for c in site.categories if c.name.lower() == query)
                   for p in site.products)
    session = asyncio.run(run_session(site, shopper, ModelPolicy(_FakeModel(query=query), vision=False),
                                     seed=3, max_steps=2, render=False))
    assert session.searches[0].query == query and session.searches[0].results == expected > 0
    assert session.steps[0].choice.kind == ActionKind.SEARCH and session.steps[0].source == "model"


def test_a_single_search_result_reads_as_one_result():
    from store_emulator.domain.online import PageKind, PageRef
    from store_emulator.engine.online.browser import build_page, initial_state

    site = _site(welcome_popup="none")
    name = next(p.name for p in site.products if len(search_products(site, p.name)) == 1)
    state = initial_state(site).model_copy(update={"at": PageRef(page=PageKind.SEARCH, query=name)})
    notes = [g.note for g in build_page(site, state).grids if g.note]
    assert notes and notes[0].startswith("1 result · page 1 of 1")
