"""Unambiguous spelling variants must not exhaust automatic starter selection."""

import asyncio
import json

import httpx
import pytest
from openai import AsyncOpenAI
from pydantic import ValidationError

from store_emulator.domain.config import LLMConfig
from store_emulator.engine import llm_client
from store_emulator.engine.starter_fill import fill_empty_racks, rack_choices
from store_emulator.engine.starter_selection import select_starter_products
from tests.engine.test_starter_selection import empty_store


@pytest.mark.parametrize("mode", ["json", "json_schema"])
@pytest.mark.parametrize("path", ["primary", "small"])
@pytest.mark.parametrize("field", ["category", "rack", "sku", "all"])
@pytest.mark.parametrize("spelling", ["uppercase", "whitespace"])
def test_http_identifier_variants_reach_exact_catalog_placements_and_cache(monkeypatch, tmp_path, mode, path, field, spelling):
    store = empty_store("KRW")
    before = store.model_dump()
    original, calls = llm_client.litellm.acompletion, []
    category = "home_coffee_tea"

    def variant(value, kind):
        if field not in {kind, "all"}:
            return value
        return value.upper() if spelling == "uppercase" else f"\u3000{value}\n"

    def respond(request):
        body = json.loads(request.content)
        calls.append(body)
        # Semantic correction requests retain a complete JSON context; schema
        # retries are not expected for these ordinary string-valued variants.
        context = json.loads(next(m["content"] for m in body["messages"] if m["role"] == "user"))
        system = body["messages"][0]["content"]
        if "Choose one catalog category" in system:
            answer = {"choices": [variant(category, "category")] * len(context["racks"])}
        elif "ONE supplied category" in system:
            answer = {"choices": [variant(context["categories"][category][0]["sku"], "sku")]}
        elif "racks" in context:
            ids = [variant(r["id"], "rack") for r in context["racks"]]
            answer = {"groups": [{"category": variant(category, "category"),
                "rack_ids": ["invented_rack"] if path == "small" else ids}]}
        else:
            answer = {"groups": [{"category": variant(category, "category"), "skus": [
                "invented_sku" if path == "small" else variant(context["categories"][category][0]["sku"], "sku")]}]}
        return httpx.Response(200, request=request, json={"id": "offline", "object": "chat.completion", "created": 0,
            "model": body["model"], "choices": [{"index": 0, "finish_reason": "stop",
                "message": {"role": "assistant", "content": json.dumps(answer)}}]})

    async def exercise():
        async with httpx.AsyncClient(transport=httpx.MockTransport(respond)) as http:
            adapter = AsyncOpenAI(api_key="offline", base_url="http://127.0.0.1:8081/v1", http_client=http, max_retries=0)

            async def completion(**kwargs):
                return await original(**{**kwargs, "client": adapter, "api_key": "offline", "num_retries": 0})

            monkeypatch.setattr(llm_client.litellm, "acompletion", completion)
            client = llm_client.LiteLLMClient(LLMConfig(model="openai/starter-identifiers", api_base="http://127.0.0.1:8081/v1",
                structured_output=mode, cache_dir=str(tmp_path)))
            for repeat in range(2):
                assignments = await select_starter_products(client, store, rack_choices(store), "동네 주민을 위한 커피",
                    allowed_categories={category})
                assert {row.rack_id for row in assignments} == {"a", "b"}
                assert all(row.category == category and row.skus and row.skus[0].startswith("g_") for row in assignments)
                stocked, report = fill_empty_racks(store, assignments, 2)
                assert report.new_skus == 1 and report.placements_added > 0
                assert all(item.sku == assignments[0].skus[0]
                    for rack in stocked.racks for slot in rack.slots for item in slot.items)
                expected = 2 if path == "primary" else 6
                assert len(calls) == expected
                assert client.get_usage().cached_requests == repeat * expected
                assert store.model_dump() == before

    asyncio.run(exercise())


@pytest.mark.parametrize("spelling", ["exact", "ambiguous"])
def test_case_distinct_racks_stay_distinct_and_ambiguous_ids_use_positional_recovery(spelling):
    store = empty_store()
    store.racks[2].id, store.racks[3].id = "Case", "case"
    calls = []

    class Model:
        async def generate_structured_async(self, schema, system, user, **kwargs):
            data = json.loads(user)
            calls.append(data)
            if "choices" in schema.model_fields:
                answer = {"choices": ["home_coffee_tea"] * len(data["racks"])}
            elif "racks" in data:
                ids = [r["id"] for r in data["racks"]]
                answer = {"groups": [{"category": "home_coffee_tea",
                    "rack_ids": ids if spelling == "exact" else [rid.upper() for rid in ids]}]}
            else:
                answer = {"groups": [{"category": key, "skus": [products[0]["sku"]]}
                    for key, products in data["categories"].items()]}
            return schema.model_validate(answer)

    assignments = asyncio.run(select_starter_products(Model(), store, rack_choices(store), "Coffee",
        allowed_categories={"home_coffee_tea"}))
    assert sorted(row.rack_id for row in assignments) == ["Case", "case"]
    assert len(calls) == (2 if spelling == "exact" else 4)
    if spelling == "ambiguous":
        assert "CASE" in calls[1]["correction"]["error"] and "position" in calls[2]["racks"][0]


def test_spelling_recovery_never_deduplicates_sku_choices():
    store = empty_store()
    before, calls = store.model_dump(), []

    class Model:
        async def generate_structured_async(self, schema, system, user, **kwargs):
            data = json.loads(user)
            calls.append(data)
            if "racks" in data:
                answer = {"groups": [{"category": "HOME_COFFEE_TEA", "rack_ids": [r["id"] for r in data["racks"]]}]}
            else:
                sku = data["categories"]["home_coffee_tea"][0]["sku"]
                values = [sku, sku.upper()]
                answer = ({"choices": values} if "choices" in schema.model_fields else
                          {"groups": [{"category": "HOME_COFFEE_TEA", "skus": values}]})
            return schema.model_validate(answer)

    with pytest.raises(ValueError, match="requested selection format") as caught:
        asyncio.run(select_starter_products(Model(), store, rack_choices(store), "Coffee",
            allowed_categories={"home_coffee_tea"}))
    # Small choices now reject duplicates inside model validation, before the
    # outer semantic-correction pass or any cache write.
    cause = caught.value.__cause__
    assert isinstance(cause, ValidationError)
    assert any("Select each SKU only once" in error["msg"] for error in cause.errors(include_input=False))
    assert len(calls) == 4 and store.model_dump() == before


def test_exact_whitespace_ids_take_precedence_over_trimmed_aliases():
    store = empty_store()
    store.racks[2].id, store.racks[3].id = " case ", "case"
    calls = []

    class Model:
        async def generate_structured_async(self, schema, system, user, **kwargs):
            data = json.loads(user)
            calls.append(data)
            if "racks" in data:
                answer = {"groups": [{"category": "home_coffee_tea", "rack_ids": [r["id"] for r in data["racks"]]}]}
            else:
                answer = {"groups": [{"category": key, "skus": [products[0]["sku"]]}
                    for key, products in data["categories"].items()]}
            return schema.model_validate(answer)

    assignments = asyncio.run(select_starter_products(Model(), store, rack_choices(store), "Coffee",
        allowed_categories={"home_coffee_tea"}))
    assert sorted(row.rack_id for row in assignments) == [" case ", "case"] and len(calls) == 2
