"""A model that cannot copy resource identifiers can still choose catalog entries."""

import asyncio
import json
from collections import Counter

import pytest

from store_emulator.domain.starter_fill import StarterRack
from store_emulator.engine.layout_gen.catalog import CATALOG, catalog_slot_item
from store_emulator.engine.starter_selection import CategorySelection, ProductSelection, select_starter_products
from tests.engine.test_starter_selection import empty_store


class SmallTaskModel:
    def __init__(self, *, category_fault=True, product_fault=True, bad_small=None):
        self.category_fault = category_fault
        self.product_fault = product_fault
        self.bad_small = bad_small
        self.calls = []

    async def generate_structured_async(self, schema, system, user, **kwargs):
        payload = json.loads(user)
        self.calls.append((schema, payload, system))
        if issubclass(schema, CategorySelection):
            ids = [r["id"] for r in payload["racks"]]
            if self.category_fault:
                # The reported local-model error: omit section_0, invent other sections.
                ids = ["section_10", "section_11", "section_12", "section_999"]
            return schema.model_validate({"groups": [{"category": "home_coffee_tea", "rack_ids": ids}]})
        if issubclass(schema, ProductSelection):
            return schema.model_validate({"groups": [{"category": k, "skus":
                ["invented_sku"] if self.product_fault else [products[0]["sku"]]}
                for k, products in payload["categories"].items()]})
        properties = schema.model_json_schema()["properties"]["choices"]
        allowed = properties["items"]["enum"]
        if "racks" in payload:
            assert 1 <= len(payload["racks"]) <= 8
            assert all("id" not in r for r in payload["racks"])
            assert properties["minItems"] == properties["maxItems"] == len(payload["racks"])
            values = ["home_coffee_tea"] * len(payload["racks"])
        else:
            assert len(payload["categories"]) == 1
            values = [allowed[0]]
        if self.bad_small == "unknown": values[0] = "invented"
        elif self.bad_small == "short": values = []
        elif self.bad_small == "long": values *= 17
        elif self.bad_small == "duplicate" and "racks" not in payload: values *= 2
        return schema.model_validate({"choices": values})


@pytest.mark.parametrize("count", [1, 2, 8, 9, 16, 99, 100])
@pytest.mark.parametrize("currency", ["USD", "KRW", "JPY"])
def test_repeated_invented_sections_and_products_recover_with_small_bound_tasks(count, currency):
    store = empty_store(currency)
    before = store.model_dump()
    racks = [StarterRack(id=f"section_{i}", name=f"선반 {i} (20 racks)", type="shelf", available_slots=4)
             for i in range(count)]
    model = SmallTaskModel()
    chosen = asyncio.run(select_starter_products(model, store, racks, "동네 주민; exclude alcohol",
        allowed_categories={"home_coffee_tea", "dairy"}, product_limits={"home_coffee_tea": 2}))
    assert Counter(r.rack_id for r in chosen) == Counter(r.id for r in racks)
    valid = {catalog_slot_item(p, currency).sku for p in CATALOG["home_coffee_tea"]}
    assert all(r.category == "home_coffee_tea" and len(r.skus) == 1 and set(r.skus) <= valid for r in chosen)
    assert len(model.calls) == 5 + (count + 7) // 8
    assert all("동네 주민" in payload["requirements"] for _, payload, _ in model.calls)
    assert store.model_dump() == before


@pytest.mark.parametrize("bad", ["unknown", "short", "long", "duplicate"])
def test_invalid_small_answers_never_escape_catalog_or_save_partial_assignments(bad):
    store = empty_store()
    before = store.model_dump()
    model = SmallTaskModel(bad_small=bad)
    with pytest.raises(ValueError):
        asyncio.run(select_starter_products(model, store, [StarterRack(id="section_0", name="Shelf", type="shelf", available_slots=2)], ""))
    assert len(model.calls) <= 8
    assert store.model_dump() == before


@pytest.mark.parametrize("error", [TimeoutError("offline"), ValueError("bad provider configuration")])
def test_provider_failure_during_small_tasks_stops_without_further_model_calls(error):
    class Offline(SmallTaskModel):
        async def generate_structured_async(self, schema, system, user, **kwargs):
            if not issubclass(schema, CategorySelection):
                self.calls.append((schema, json.loads(user), system))
                raise error
            return await super().generate_structured_async(schema, system, user, **kwargs)
    model = Offline()
    with pytest.raises(type(error), match=str(error)):
        asyncio.run(select_starter_products(model, empty_store(), [StarterRack(id="section_0", name="Shelf", type="shelf", available_slots=2)], ""))
    assert len(model.calls) == 3


@pytest.mark.parametrize("kind", ["schema", "json", "truncated", "wrapped_schema", "wrapped_timeout"])
def test_malformed_bulk_replies_decompose_but_wrapped_connection_failures_do_not(kind):
    from instructor.core.exceptions import FailedAttempt, IncompleteOutputException, InstructorRetryException
    from pydantic import ValidationError

    try:
        CategorySelection.model_validate({})
    except ValidationError as exc:
        invalid = exc
    if kind == "schema": error = invalid
    elif kind == "json": error = json.JSONDecodeError("missing JSON", "", 0)
    elif kind == "truncated": error = IncompleteOutputException()
    else:
        cause = TimeoutError("offline") if kind == "wrapped_timeout" else invalid
        error = InstructorRetryException("retries exhausted", n_attempts=2, total_usage=0,
                                        failed_attempts=[FailedAttempt(1, cause)])

    class BrokenBulk(SmallTaskModel):
        async def generate_structured_async(self, schema, system, user, **kwargs):
            if issubclass(schema, CategorySelection):
                self.calls.append((schema, json.loads(user), system))
                raise error
            return await super().generate_structured_async(schema, system, user, **kwargs)

    model = BrokenBulk(product_fault=False)
    task = select_starter_products(model, empty_store(), [StarterRack(id="section_0", name="Shelf", type="shelf", available_slots=2)], "")
    if kind == "wrapped_timeout":
        with pytest.raises(InstructorRetryException): asyncio.run(task)
        assert len(model.calls) == 1
    else:
        chosen = asyncio.run(task)
        assert len(chosen) == 1 and chosen[0].rack_id == "section_0"
        assert len(model.calls) == 3


def test_small_batches_share_the_sixteen_category_budget_and_keep_unusual_ids_exact():
    class Diverse(SmallTaskModel):
        async def generate_structured_async(self, schema, system, user, **kwargs):
            payload = json.loads(user)
            if "choices" in schema.model_fields and "racks" in payload:
                self.calls.append((schema, payload, system))
                allowed = schema.model_json_schema()["properties"]["choices"]["items"]["enum"]
                previous = payload["already_selected_categories"]
                new = [key for key in allowed if key not in previous]
                if len(previous) == 16:
                    assert set(allowed) == set(previous)
                values = (new or allowed)[:len(payload["racks"])]
                return schema.model_validate({"choices": values})
            return await super().generate_structured_async(schema, system, user, **kwargs)

    ids = ["진열대 🌿", "__proto__", "a/b", "Case", "case", *[f"section_{i}" for i in range(19)]]
    racks = [StarterRack(id=rid, name="Shelf", type="shelf", available_slots=2) for rid in ids]
    model = Diverse(product_fault=False)
    chosen = asyncio.run(select_starter_products(model, empty_store(), racks, "", allowed_categories=set(sorted(CATALOG)[:20])))
    assert Counter(row.rack_id for row in chosen) == Counter(ids)
    assert len({row.category for row in chosen}) == 16


def test_recovered_answers_are_cached_with_their_bounded_schema(tmp_path, monkeypatch):
    from types import SimpleNamespace
    from store_emulator.domain.config import LLMConfig
    from store_emulator.engine.llm_client import LiteLLMClient

    fake = SmallTaskModel()
    client = LiteLLMClient(LLMConfig(model="openai/local", api_base="http://127.0.0.1:9/v1", cache_dir=str(tmp_path)))

    async def create(schema, messages, max_retries, seed, max_tokens):
        result = await fake.generate_structured_async(schema, messages[0]["content"], messages[1]["content"])
        return result, SimpleNamespace(usage=None)

    monkeypatch.setattr(client, "_acreate", create)
    racks = [StarterRack(id="section_0", name="Shelf", type="shelf", available_slots=2)]
    first = asyncio.run(select_starter_products(client, empty_store(), racks, "동네 주민"))
    count = len(fake.calls)
    second = asyncio.run(select_starter_products(client, empty_store(), racks, "동네 주민"))
    assert first == second and len(fake.calls) == count == 6
    assert client.get_usage().cached_requests == count
