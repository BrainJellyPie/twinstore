"""Catalog search keeps ordered matching semantics without repeating the catalog's text work."""

import difflib

import pytest

from store_emulator.engine.capture import catalog_match as matching
from store_emulator.engine.layout_gen.catalog import CatalogItem
from store_emulator.engine.shelf_lab import rival
from tests.engine.test_rival_comparison_boundaries import pair


def exhaustive(name, categories):
    """The original exhaustive comparison, used as an independent optimization oracle."""
    query = matching.normalize_text(name)
    if not query:
        return None
    query_without_size = " ".join(matching.tokens(name))
    best = None
    for cat in categories or list(matching.CATALOG):
        for item in matching.CATALOG.get(cat, []):
            for text in (item.en, item.ko):
                score = difflib.SequenceMatcher(None, query, matching.normalize_text(text)).ratio()
                if query == query_without_size and query == " ".join(matching.tokens(text)):
                    score = 1.0
                if score == 1.0:
                    return cat, item, score
                if best is None or score > best[2]:
                    best = cat, item, score
    return best


@pytest.mark.parametrize("name", ["Cola 500ml", "Ginger Ale", "캔커피 175ml", "Ｃｏｌａ　５００ｍｌ",
                                  "Takis Fuego 9.9oz", "Salmon Nigiri 2pc", "!!!", ""])
@pytest.mark.parametrize("categories", [None, [], ["dairy", "soft_drinks"], ["missing"]])
def test_optimized_search_matches_exhaustive_catalog_order(name, categories):
    assert matching.best_catalog_item(name, categories) == exhaustive(name, categories)


@pytest.mark.parametrize("categories", [None, ["b", "a"], ["a", "b"], ["b", "b"]])
@pytest.mark.parametrize("name", ["Drink", "Drink 500ml", "Drnik", "A"])
def test_ties_pack_sizes_and_changed_catalog_entries_keep_order(monkeypatch, categories, name):
    monkeypatch.setattr(matching, "CATALOG", {
        "a": [CatalogItem("Drink 500ml", "음료 500ml", 100), CatalogItem("Z", "Z", 200)],
        "b": [CatalogItem("Drink", "음료", 300), CatalogItem("Drink 500ml", "음료 500ml", 400)],
    })
    assert matching.best_catalog_item(name, categories) == exhaustive(name, categories)
    matching.CATALOG["a"] = list(reversed(matching.CATALOG["a"]))
    assert matching.best_catalog_item(name, categories) == exhaustive(name, categories)


def test_matching_another_label_does_not_renormalize_the_catalog(monkeypatch):
    matching.best_catalog_item("Unknown warmup label")
    calls = []
    original = matching.normalize_text

    def observed(text):
        calls.append(text)
        return original(text)

    monkeypatch.setattr(matching, "normalize_text", observed)
    assert matching.best_catalog_item("A different unknown label") is not None
    assert len(calls) <= 2


def test_uncategorized_rival_comparison_does_not_classify_unused_categories(monkeypatch):
    store, capture = pair(our_name="Tea", rival_name="Tea", our_price=200, rival_price=100)

    def unexpected(*args):
        pytest.fail("An unfiltered price comparison need not classify the store's products")

    monkeypatch.setattr(rival, "_category_of", unexpected)
    result = rival.compare_rival(store, capture)
    assert result.price_index == 0.5 and result.matched == result.our_products_in_categories == 1
    assert result.overlap == 1
