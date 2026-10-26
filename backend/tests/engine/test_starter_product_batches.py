"""Large failed catalogs recover in bounded groups without relaxing product validation."""
import asyncio
import json
from types import SimpleNamespace

import pytest
from litellm.exceptions import AuthenticationError, ContextWindowExceededError

from store_emulator.domain.config import LLMConfig
from store_emulator.domain.starter_fill import StarterRack
from store_emulator.engine.layout_gen.catalog import CATALOG, catalog_slot_item
from store_emulator.engine.llm_client import LiteLLMClient
from store_emulator.engine.starter_selection import CategorySelection, select_starter_products
from tests.engine.test_starter_selection import empty_store


KEYS = list(CATALOG)[:12]


class BoundedModel:
    def __init__(self, maximum=3, fault="context"):
        self.maximum, self.fault = maximum, fault
        self.calls = []

    async def generate_structured_async(self, schema, system, user, **kwargs):
        payload = json.loads(user)
        if issubclass(schema, CategorySelection):
            return schema.model_validate({"assignments": {str(i): key for i, key in enumerate(KEYS)}})
        categories = payload["categories"]
        keys = list(categories)
        self.calls.append(keys)
        if "choices" in schema.model_fields:
            return schema.model_validate({"choices": [categories[keys[0]][-1]["sku"]]})
        if len(keys) == len(KEYS) or len(keys) > self.maximum:
            raise ContextWindowExceededError("input exceeds the available context", model="local", llm_provider="openai")
        if self.fault == "auth":
            raise AuthenticationError("authentication expired", model="local", llm_provider="openai")
        wire = schema.model_json_schema()["properties"]["selections"]
        assert set(wire["properties"]) == set(wire["required"]) == set(keys)
        assert set(payload["maximum_products_per_category"]) == set(keys)
        for key in keys:
            field = wire["properties"][key]
            assert field["maxItems"] == 1
            assert set(field["items"]["enum"]) == {p["sku"] for p in categories[key]}
        choices = {key: [categories[key][-1]["sku"]] for key in keys}
        if self.fault == "wrong_category":
            choices[keys[0]] = choices[keys[1]]
        elif self.fault == "missing":
            choices.pop(keys[0])
        elif self.fault == "duplicate":
            choices[keys[0]] *= 2
        return schema.model_validate({"selections": choices})


def select(model, store):
    racks = [StarterRack(id=str(i), name=key, type="shelf", available_slots=4) for i, key in enumerate(KEYS)]
    return select_starter_products(model, store, racks, "Local residents", allowed_categories=set(KEYS),
                                   product_limits=dict.fromkeys(KEYS, 1))


def test_overflow_shrinks_batches_and_keeps_each_successful_selection():
    store = empty_store("JPY")
    before = store.model_dump()
    model = BoundedModel()
    selected = asyncio.run(select(model, store))
    assert [len(keys) for keys in model.calls] == [12, 6, 3, 3, 3, 3]
    assert [(row.rack_id, row.category) for row in selected] == list(zip(map(str, range(12)), KEYS))
    assert all(row.skus == [catalog_slot_item(CATALOG[row.category][-1], "JPY").sku] for row in selected)
    assert store.model_dump() == before


@pytest.mark.parametrize("fault", ["wrong_category", "missing", "duplicate"])
def test_invalid_batch_still_reaches_valid_single_category_recovery(fault):
    model = BoundedModel(maximum=6, fault=fault)
    selected = asyncio.run(select(model, empty_store()))
    assert [len(keys) for keys in model.calls[:5]] == [12, 6, 6, 3, 3]
    assert model.calls[5:] == [[key] for key in KEYS]
    assert all(row.skus == [catalog_slot_item(CATALOG[row.category][-1], "USD").sku] for row in selected)


def test_authentication_failure_during_a_batch_does_not_decompose_or_mutate_store():
    model = BoundedModel(maximum=6, fault="auth")
    store = empty_store()
    before = store.model_dump()
    with pytest.raises(AuthenticationError):
        asyncio.run(select(model, store))
    assert [len(keys) for keys in model.calls] == [12, 6]
    assert store.model_dump() == before


def test_partial_primary_choices_survive_batched_recovery_and_cache_replay(tmp_path, monkeypatch):
    class Partial(BoundedModel):
        async def generate_structured_async(self, schema, system, user, **kwargs):
            payload = json.loads(user)
            if not issubclass(schema, CategorySelection) and len(payload["categories"]) == len(KEYS):
                self.calls.append(list(payload["categories"]))
                return schema.model_validate({"selections": {
                    key: [payload["categories"][key][0]["sku"]] for key in KEYS[:6]}})
            return await super().generate_structured_async(schema, system, user, **kwargs)

    model = Partial()
    client = LiteLLMClient(LLMConfig(model="openai/local", api_base="http://127.0.0.1:9/v1", cache_dir=str(tmp_path)))

    async def create(schema, messages, max_retries, seed, max_tokens):
        return await model.generate_structured_async(schema, messages[0]["content"], messages[1]["content"]), SimpleNamespace(usage=None)

    monkeypatch.setattr(client, "_acreate", create)
    first = asyncio.run(select(client, empty_store("KRW")))
    assert model.calls == [KEYS, KEYS[6:9], KEYS[9:12]]
    for row in first:
        index = 0 if row.category in KEYS[:6] else -1
        assert row.skus == [catalog_slot_item(CATALOG[row.category][index], "KRW").sku]
    assert asyncio.run(select(client, empty_store("KRW"))) == first
    assert len(model.calls) == 3 and client.get_usage().cached_requests == 4


def test_failed_later_batch_does_not_expose_an_incomplete_assortment():
    class Disconnected(BoundedModel):
        async def generate_structured_async(self, schema, system, user, **kwargs):
            if len(self.calls) == 3:
                raise TimeoutError("model disconnected after the first successful batch")
            return await super().generate_structured_async(schema, system, user, **kwargs)

    store = empty_store()
    before = store.model_dump()
    model = Disconnected()
    with pytest.raises(TimeoutError):
        asyncio.run(select(model, store))
    assert [len(keys) for keys in model.calls] == [12, 6, 3]
    assert store.model_dump() == before
