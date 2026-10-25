"""Multiple shelf placements must not become multiple products in an online shop."""

import pytest

from store_emulator.domain.rack import Slot
from store_emulator.domain.store import Store
from store_emulator.domain.types import Face
from store_emulator.engine.layout_gen import generate_store
from store_emulator.engine.online.catalog import site_from_store


@pytest.mark.parametrize("currency", ["USD", "KRW", "JPY"])
@pytest.mark.parametrize("template", ["station_kiosk", "specialty_cafe", "urban_cvs"])
def test_generated_layout_import_keeps_each_sku_and_its_first_offer_once(template, currency):
    store = generate_store(template, currency=currency)
    original = store.model_dump()
    first = {}
    for rack in store.racks:
        for slot in rack.slots:
            for item in slot.items:
                first.setdefault(item.sku, item)
    site = site_from_store(store, site_id="imported", name="Imported", currency=currency)
    assert [p.sku for p in site.products] == list(first)
    assert [p.id for p in site.products] == [f"p{i + 1:03d}" for i in range(len(first))]
    for product in site.products:
        source = first[product.sku]
        assert (product.name, product.price, product.image_url) == (source.name[:120], source.price, source.image_url or "")
        assert product.list_price == (source.regular_price if source.regular_price > source.price else 0)
    assert store.model_dump() == original and site.currency == currency


@pytest.mark.parametrize("placement", ["level", "face", "block", "same_slot", "rack", "mixed"])
@pytest.mark.parametrize("currency", ["USD", "KRW", "JPY"])
def test_repeated_sku_keeps_first_placement_price_photo_and_category(collision_store, placement, currency):
    store = collision_store
    rack, other = store.racks[:2]
    rack.rack_name, other.rack_name = "First shelf", "Another shelf"
    first = rack.slots[0].items[0]
    first.price, first.regular_price, first.image_url = 100, 200, "/first.png"
    repeat = first.model_copy(update={"name": "Later offer", "price": 999, "regular_price": 1200, "image_url": "/later.png"})
    if placement in {"level", "mixed"}:
        rack.slots.append(Slot(block=0, face=Face.E, level=2, items=[repeat]))
    elif placement == "face":
        rack.slots.append(Slot(block=0, face=Face.S, level=1, items=[repeat]))
    elif placement == "block":
        rack.shape = [[1, 1]]
        rack.slots.append(Slot(block=1, face=Face.S, level=1, items=[repeat]))
    elif placement == "same_slot":
        rack.slots[0].items.append(repeat)
    if placement in {"rack", "mixed"}:
        other.slots[0].items.append(repeat)
    store = Store.model_validate(store.model_dump())
    original = store.model_dump()
    site = site_from_store(store, site_id="imported", name="Imported", currency=currency)
    assert [p.sku for p in site.products] == [first.sku, other.slots[0].items[0].sku]
    assert (site.products[0].name, site.products[0].price, site.products[0].list_price,
            site.products[0].image_url) == (first.name, 100, 200, "/first.png")
    assert site.category(site.products[0].category_id).name == "First shelf"
    assert store.model_dump() == original


def test_distinct_skus_with_identical_names_and_prices_remain_distinct(collision_store):
    store = collision_store
    first = store.racks[0].slots[0].items[0]
    store.racks[0].slots[0].items.append(first.model_copy(update={"sku": "another_sku"}))
    site = site_from_store(store, site_id="imported", name="Imported", currency="USD")
    assert [p.sku for p in site.products] == [first.sku, "another_sku", "sku-b"]
