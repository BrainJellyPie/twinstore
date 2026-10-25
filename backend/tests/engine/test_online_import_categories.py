"""Shelf labels must not merge because their URL-like spellings collide."""

import pytest

from store_emulator.engine.online.catalog import site_from_store


@pytest.mark.parametrize("labels", [
    ("Fresh & Frozen", "Fresh / Frozen"), ("🍎", "🥛"),
    ("A" * 40 + " fruit", "A" * 40 + " dairy"),
    ("매우 긴 상품 분류 이름 " * 4 + "과일", "매우 긴 상품 분류 이름 " * 4 + "우유"),
    ("精选商品分类" * 8 + "水果", "精选商品分类" * 8 + "牛奶"),
    ("おすすめ商品分類" * 6 + "果物", "おすすめ商品分類" * 6 + "乳製品"),
])
def test_distinct_shelf_labels_keep_distinct_categories(collision_store, labels):
    store = collision_store
    for rack, label in zip(store.racks[:2], labels, strict=True):
        rack.rack_name = label
    original = store.model_dump()
    site = site_from_store(store, site_id="imported", name="Imported", currency="USD")
    assert len(site.categories) == 2
    assert [category.name for category in site.categories] == [label[:80] for label in labels]
    assert len({product.category_id for product in site.products}) == 2
    assert [site.category(product.category_id).name for product in site.products] == [label[:80] for label in labels]
    assert store.model_dump() == original
    assert site.model_dump() == site_from_store(store, site_id="imported", name="Imported", currency="USD").model_dump()


@pytest.mark.parametrize("labels", [("Dairy", "Dairy"), ("Dairy 1", "Dairy 2"), ("Dairy", "DAIRY")])
def test_repeated_signs_still_share_their_category(collision_store, labels):
    for rack, label in zip(collision_store.racks[:2], labels, strict=True):
        rack.rack_name = label
    site = site_from_store(collision_store, site_id="imported", name="Imported", currency="USD")
    assert len(site.categories) == 1
    assert len(site.products) == 2
    assert len({product.category_id for product in site.products}) == 1
