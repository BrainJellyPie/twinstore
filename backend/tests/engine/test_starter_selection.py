import asyncio
import json

import pytest

from store_emulator.domain.rack import Rack
from store_emulator.domain.starter_fill import RackFill
from store_emulator.domain.store import Store
from store_emulator.engine.layout_gen.catalog import CATALOG, catalog_slot_item
from store_emulator.engine.starter_fill import fill_empty_racks, rack_choices
from store_emulator.engine.starter_selection import CategorySelection, select_starter_products


def empty_store(currency="USD"):
    return Store(id="test", name="Test", type="cafe", currency=currency, grid_size=(8, 8), racks=[
        Rack(id="entry", type="entrance", shape=[[1]], position=(0, 7)),
        Rack(id="exit", type="exit", shape=[[1]], position=(0, 7)),
        Rack(id="a", type="shelf", shape=[[1]], position=(3, 3)),
        Rack(id="b", type="fridge", shape=[[1]], position=(1, 0)),
    ])


class FakeModel:
    def __init__(self, category="home_coffee_tea", edit=None):
        self.category, self.edit, self.calls = category, edit, []

    async def generate_structured_async(self, response_model, system_prompt, user_prompt, **kwargs):
        source = json.loads(user_prompt)
        self.calls.append(source)
        if response_model is CategorySelection:
            data = {"groups": [{"category": self.category, "rack_ids": [r["id"] for r in source["racks"]]}]}
        else:
            data = {"groups": [{"category": self.category, "skus": [p["sku"] for p in source["categories"][self.category]][:3]}]}
        if self.edit:
            self.edit(data, len(self.calls))
        return response_model.model_validate(data)


@pytest.mark.parametrize("category", CATALOG)
@pytest.mark.parametrize("currency", ["USD", "KRW", "JPY"])
def test_each_category_selects_only_catalog_products_and_preserves_currency(category, currency):
    store = empty_store(currency)
    model = FakeModel(category)
    choices = asyncio.run(select_starter_products(model, store, rack_choices(store), "다양한 기본 상품 🌿"))
    assert len(model.calls) == 2 and model.calls[1]["requirements"] == "다양한 기본 상품 🌿"
    candidates = model.calls[1]["categories"][category]
    assert len(candidates) == len(CATALOG[category])
    for source, candidate in zip(CATALOG[category], candidates):
        assert candidate["image_available"] is bool(catalog_slot_item(source, currency).image_url)
    result, report = fill_empty_racks(store, choices, 4)
    expected = {catalog_slot_item(p, currency).sku: catalog_slot_item(p, currency) for p in CATALOG[category][:3]}
    assert {p.sku for r in report.racks for p in r.products} == set(expected)
    assert all(p == expected[p.sku] for r in result.racks for s in r.slots for p in s.items)
    assert not any(r.slots for r in store.racks)
    assert all(len(s.items) == len({p.sku for p in s.items}) == 3 for r in result.racks for s in r.slots)


@pytest.mark.parametrize("fault", ["unknown_category", "duplicate_category", "unknown_rack", "missing_rack", "duplicate_rack", "unknown_sku", "wrong_category_sku", "duplicate_sku", "missing_products", "duplicate_product_category", "empty_products"])
def test_invalid_model_choices_never_produce_partial_placements(fault):
    def edit(data, call):
        group = data["groups"][0]
        if call == 1:
            if fault == "unknown_category": group["category"] = "injected"
            if fault == "duplicate_category": data["groups"].append(group.copy())
            if fault == "unknown_rack": group["rack_ids"] = ["unknown", "b"]
            if fault == "missing_rack": group["rack_ids"] = ["a"]
            if fault == "duplicate_rack": group["rack_ids"] = ["a", "a", "b"]
        else:
            if fault == "unknown_sku": group["skus"] = ["injected"]
            if fault == "wrong_category_sku": group["skus"] = [catalog_slot_item(CATALOG["dairy"][0], "USD").sku]
            if fault == "duplicate_sku": group["skus"] *= 2
            if fault == "missing_products": group["category"] = "dairy"
            if fault == "duplicate_product_category": data["groups"].append(group.copy())
            if fault == "empty_products": group["skus"] = []
    store = empty_store()
    with pytest.raises(ValueError):
        asyncio.run(select_starter_products(FakeModel(edit=edit), store, rack_choices(store), ""))
    assert not any(r.slots for r in store.racks)


def test_empty_or_excessive_racks_fail_before_calling_model():
    store = empty_store()
    model = FakeModel()
    for racks in ([], [rack_choices(store)[0].model_copy(update={"id": str(i)}) for i in range(101)]):
        with pytest.raises(ValueError):
            asyncio.run(select_starter_products(model, store, racks, ""))
    assert model.calls == []


def test_different_selected_products_in_same_category_keep_their_own_order():
    store = empty_store()
    ids = [catalog_slot_item(p, "USD").sku for p in CATALOG["home_coffee_tea"]]
    rows = [RackFill(rack_id="a", category="home_coffee_tea", skus=ids[:2]), RackFill(rack_id="b", category="home_coffee_tea", skus=ids[2:5])]
    _, report = fill_empty_racks(store, rows, 4)
    assert [p.sku for p in report.racks[0].products] == ids[:2]
    assert [p.sku for p in report.racks[1].products] == ids[2:5]


@pytest.mark.parametrize("per_slot", [1, 2, 3, 4])
def test_model_selection_cannot_exceed_the_available_sections(per_slot):
    store = empty_store()
    rack = rack_choices(store)[0].model_copy(update={"available_slots": 1})
    def edit(data, call):
        if call == 2:
            data["groups"][0]["skus"] = [catalog_slot_item(p, "USD").sku for p in CATALOG["home_coffee_tea"][:per_slot + 1]]
    model = FakeModel(edit=edit)
    with pytest.raises(ValueError, match="shelf capacity"):
        asyncio.run(select_starter_products(model, store, [rack], "", products_per_slot=per_slot))
    assert model.calls[1]["maximum_products_per_category"] == {"home_coffee_tea": per_slot}
