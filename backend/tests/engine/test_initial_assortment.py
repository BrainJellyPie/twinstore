import json

import pytest

from store_emulator.application import template_assortment
from store_emulator.domain.config import SimulationConfig
from store_emulator.domain.layout_options import TemplateLayoutRequest
from store_emulator.engine.layout_gen import TEMPLATES, generate_store
from store_emulator.engine.layout_gen.catalog import catalog_slot_item, CATALOG, category_label
from store_emulator.engine.starter_selection import CategorySelection
from store_emulator.engine.validation import validate


class Model:
    def __init__(self): self.calls = []

    async def generate_structured_async(self, schema, system, user, **kwargs):
        payload = json.loads(user); self.calls.append(payload)
        if schema is CategorySelection:
            allowed = {c["id"] for c in payload["categories"]}
            groups = {}
            for rack in payload["racks"]:
                key = "dairy" if rack["type"] == "fridge" else "home_coffee_tea"
                if key not in allowed: key = sorted(allowed)[0]
                groups.setdefault(key, []).append(rack["id"])
            data = {"groups": [{"category": key, "rack_ids": ids} for key, ids in groups.items()]}
        else:
            data = {"groups": [{"category": key, "skus": [p["sku"] for p in products[:min(2, payload["maximum_products_per_category"][key])]]} for key, products in payload["categories"].items()]}
        return schema.model_validate(data)


@pytest.mark.parametrize("template", TEMPLATES, ids=lambda t: t.id)
@pytest.mark.parametrize("currency", ["USD", "KRW", "JPY"])
def test_generated_formats_get_selected_catalog_products_without_changing_geometry(monkeypatch, template, currency):
    model = Model(); monkeypatch.setattr(template_assortment, "assistive_client", lambda *a: model)
    req = TemplateLayoutRequest(template_id=template.id, currency=currency)
    original = generate_store(template.id, currency=currency)
    before = original.model_dump()
    store, choices = template_assortment.select_initial_assortment(SimulationConfig(), original, req, "Local store")
    assert len(model.calls) == 2 and original.model_dump() == before and validate(store) == []
    assert store.currency == currency and store.grid_size == original.grid_size and store.weekly_schedule == original.weekly_schedule
    chosen = {row.rack_id: row for row in choices}
    for old, new in zip(original.racks, store.racks, strict=True):
        assert (old.id, old.type, old.shape, old.position, old.rotation, old.locked_faces) == (new.id, new.type, new.shape, new.position, new.rotation, new.locked_faces)
        if new.id in chosen:
            row = chosen[new.id]
            assert new.rack_desc == row.category and new.rack_name == category_label(row.category, currency)
            assert {p.sku for s in new.slots for p in s.items} == set(row.skus)
            valid = {catalog_slot_item(p, currency).sku: catalog_slot_item(p, currency) for p in CATALOG[row.category]}
            assert all(p == valid[p.sku] for s in new.slots for p in s.items)
        else:
            assert old == new


def test_large_generated_floor_groups_hundreds_of_racks_and_honors_category_limits(monkeypatch):
    model = Model(); monkeypatch.setattr(template_assortment, "assistive_client", lambda *a: model)
    req = TemplateLayoutRequest(template_id="hypermarket", width=40, height=40, density="dense", excluded_categories=["dairy"],
                                products_per_category=1, category_product_limits={"home_coffee_tea": 2})
    source = generate_store(req.template_id, options=req)
    store, choices = template_assortment.select_initial_assortment(SimulationConfig(), source, req, "Large market")
    assert len(choices) > 100 and len(model.calls[0]["racks"]) < 100
    assert all(row.category != "dairy" for row in choices)
    assert all(len(row.skus) == (2 if row.category == "home_coffee_tea" else 1) for row in choices)
    assert validate(store) == []
