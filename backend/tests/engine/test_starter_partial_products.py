"""Repair only bad category subsets without discarding valid model selections."""

import asyncio
import json
from types import SimpleNamespace

import pytest

from store_emulator.domain.config import LLMConfig
from store_emulator.domain.starter_fill import StarterRack
from store_emulator.engine.layout_gen.catalog import CATALOG, catalog_slot_item
from store_emulator.engine.llm_client import LiteLLMClient
from store_emulator.engine.starter_selection import CategorySelection, select_starter_products
from tests.engine.test_starter_selection import empty_store


KEYS = ["home_coffee_tea", "dairy", "soft_drinks"]
FAULTS = ["missing", "unknown_category", "duplicate_category", "unknown_sku", "wrong_category_sku", "duplicate_sku", "over_limit"]


class PartialModel:
    def __init__(self, fault, fail_recovery=False):
        self.fault = fault
        self.fail_recovery = fail_recovery
        self.calls = []

    async def generate_structured_async(self, schema, system, user, **kwargs):
        payload = json.loads(user)
        self.calls.append(payload)
        if issubclass(schema, CategorySelection):
            return schema.model_validate({"assignments": {str(i): key for i, key in enumerate(KEYS)}})
        categories = payload["categories"]
        if "choices" in schema.model_fields:
            key = next(iter(categories))
            return schema.model_validate({"choices": ["invalid" if self.fail_recovery else categories[key][0]["sku"]]})
        groups = [{"category": key, "skus": [categories[key][-1]["sku"]]} for key in KEYS]
        if self.fault == "missing": groups.pop(0)
        elif self.fault == "unknown_category": groups[0]["category"] = "invented_category"
        elif self.fault == "duplicate_category": groups[1] = groups[0].copy()
        elif self.fault == "unknown_sku": groups[0]["skus"] = ["invented_sku"]
        elif self.fault == "wrong_category_sku": groups[0]["skus"] = groups[1]["skus"]
        elif self.fault == "duplicate_sku": groups[0]["skus"] *= 2
        elif self.fault == "over_limit": groups[0]["skus"] = [row["sku"] for row in categories[KEYS[0]][:2]]
        elif self.fault == "all_invalid":
            for group in groups: group["skus"] = ["invented_sku"]
        elif self.fault == "unparseable": groups[0]["skus"] = []
        return schema.model_validate({"groups": groups})


def select(model, store):
    racks = [StarterRack(id=str(i), name=key, type="shelf", available_slots=4) for i, key in enumerate(KEYS)]
    return select_starter_products(model, store, racks, "Local residents", allowed_categories=set(KEYS),
                                   product_limits=dict.fromkeys(KEYS, 1))


@pytest.mark.parametrize("currency", ["USD", "KRW", "JPY"])
@pytest.mark.parametrize("fault", FAULTS)
def test_valid_subsets_survive_and_only_bad_categories_are_requested_again(currency, fault):
    store = empty_store(currency)
    before = store.model_dump()
    model = PartialModel(fault)
    selected = asyncio.run(select(model, store))
    repaired = KEYS[:2] if fault == "duplicate_category" else [] if fault == "over_limit" else KEYS[:1]
    assert len(model.calls) == 2 + len(repaired)
    assert [list(call["categories"]) for call in model.calls[2:]] == [[key] for key in repaired]
    assert not any("correction" in call for call in model.calls)
    assert [(row.rack_id, row.category) for row in selected] == list(zip(map(str, range(3)), KEYS))
    for row in selected:
        product = CATALOG[row.category][0 if row.category in repaired or fault == "over_limit" and row.category == KEYS[0] else -1]
        assert row.skus == [catalog_slot_item(product, currency).sku]
    assert store.model_dump() == before


@pytest.mark.parametrize("fault,primary_calls", [("all_invalid", 2), ("unparseable", 1)])
def test_no_usable_subset_uses_existing_bounded_full_recovery(fault, primary_calls):
    model = PartialModel(fault)
    selected = asyncio.run(select(model, empty_store()))
    assert len(model.calls) == 1 + primary_calls + len(KEYS)
    assert [list(call["categories"]) for call in model.calls[-3:]] == [[key] for key in KEYS]
    assert all(row.skus == [catalog_slot_item(CATALOG[row.category][0], "USD").sku] for row in selected)


def test_failure_repairing_one_category_returns_no_partial_result_or_store_change():
    store = empty_store()
    before = store.model_dump()
    model = PartialModel("unknown_sku", fail_recovery=True)
    with pytest.raises(ValueError):
        asyncio.run(select(model, store))
    assert len(model.calls) == 3
    assert store.model_dump() == before


def test_cached_partial_response_is_revalidated_and_reuses_only_valid_subsets(tmp_path, monkeypatch):
    model = PartialModel("unknown_sku")
    client = LiteLLMClient(LLMConfig(model="openai/local", api_base="http://127.0.0.1:9/v1", cache_dir=str(tmp_path)))

    async def create(schema, messages, max_retries, seed, max_tokens):
        return await model.generate_structured_async(schema, messages[0]["content"], messages[1]["content"]), SimpleNamespace(usage=None)

    monkeypatch.setattr(client, "_acreate", create)
    first = asyncio.run(select(client, empty_store()))
    assert len(model.calls) == 3
    assert asyncio.run(select(client, empty_store())) == first
    assert len(model.calls) == 3
    assert client.get_usage().cached_requests == 3
