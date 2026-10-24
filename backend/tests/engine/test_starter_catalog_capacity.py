"""The model's assortment limit cannot exceed the available distinct catalog products."""

import asyncio
import json

import pytest

from store_emulator.engine.layout_gen.catalog import CATALOG, catalog_slot_item
from store_emulator.engine.starter_fill import fill_empty_racks, rack_choices
from store_emulator.engine.starter_selection import CategorySelection, ProductSelection, select_starter_products
from tests.engine.test_starter_selection import empty_store


@pytest.mark.parametrize("category", ["car_care", "books", "dairy", "home_coffee_tea", "repeated"])
@pytest.mark.parametrize("currency", ["USD", "KRW", "JPY"])
@pytest.mark.parametrize("limit", [3, 16])
@pytest.mark.parametrize("fallback", [False, True])
def test_requested_maximum_is_achievable_without_repeating_products(monkeypatch, category, currency, limit, fallback):
    if category == "repeated":
        category = "car_care"
        monkeypatch.setitem(CATALOG, category, [CATALOG[category][0]] * 5)
    calls, maxima = [], []

    class Model:
        async def generate_structured_async(self, schema, system, user, **kwargs):
            payload = json.loads(user)
            calls.append(payload)
            if issubclass(schema, CategorySelection):
                return schema(groups=[{"category": category, "rack_ids": [row["id"] for row in payload["racks"]]}])
            if issubclass(schema, ProductSelection) and fallback:
                return schema(groups=[{"category": category, "skus": ["unknown-sku"]}])
            catalog = payload["categories"][category]
            maximum = (payload["maximum_products_per_category"][category] if issubclass(schema, ProductSelection)
                       else payload["maximum_products_per_category"])
            maxima.append(maximum)
            # An eager model fills the requested allowance. If it exceeds the
            # actual list, repeated valid IDs pass the grammar and fail semantics.
            values = [catalog[i % len(catalog)]["sku"] for i in range(maximum)]
            definition = schema.model_json_schema()
            if issubclass(schema, ProductSelection):
                assert definition["properties"]["groups"]["items"]["anyOf"][0]["properties"]["skus"]["maxItems"] == maximum
                return schema(groups=[{"category": category, "skus": values}])
            assert definition["properties"]["choices"]["maxItems"] == maximum
            return schema(choices=values)

    store = empty_store(currency)
    before = store.model_dump()
    rows = asyncio.run(select_starter_products(Model(), store, rack_choices(store), "Choose a varied assortment",
        allowed_categories={category}, product_limits={category: limit}))
    catalog = {catalog_slot_item(item, currency).sku for item in CATALOG[category]}
    expected = min(limit, len(catalog))
    assert maxima == [expected] and len(calls) == (4 if fallback else 2)
    assert all(len(row.skus) == len(set(row.skus)) == expected and set(row.skus) <= catalog for row in rows)
    filled, report = fill_empty_racks(store, rows, 2)
    assert len({item.sku for rack in report.racks for item in rack.products}) == expected
    assert all(len(slot.items) == len({item.sku for item in slot.items}) for rack in filled.racks for slot in rack.slots)
    assert store.model_dump() == before
