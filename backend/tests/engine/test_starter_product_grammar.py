"""The primary product grammar binds each chosen category to its own SKUs and capacity."""

import asyncio
import json

import httpx
import pytest
from jsonschema import Draft202012Validator
from openai import AsyncOpenAI

from store_emulator.domain.config import LLMConfig
from store_emulator.domain.starter_fill import StarterRack
from store_emulator.engine import llm_client
from store_emulator.engine.starter_selection import select_starter_products
from tests.engine.test_starter_selection import empty_store


@pytest.mark.parametrize("currency", ["USD", "KRW", "JPY"])
@pytest.mark.parametrize("capacities", [(1, 1), (2, 7), (20, 20)])
@pytest.mark.parametrize("reverse", [False, True])
def test_primary_http_product_grammar_rejects_wrong_catalog_choices_before_generation(monkeypatch, tmp_path, currency, capacities, reverse):
    keys = ["dairy", "home_coffee_tea"]
    if reverse:
        keys.reverse()
    racks = [StarterRack(id=f"section_{index}", name=key, type="shelf", available_slots=capacity)
             for index, (key, capacity) in enumerate(zip(keys, capacities))]
    limits = {keys[0]: 2, keys[1]: 7}
    store = empty_store(currency)
    before = store.model_dump()
    original = llm_client.litellm.acompletion
    requests = []

    def respond(request):
        body = json.loads(request.content)
        requests.append(body)
        response = body["response_format"]["json_schema"]
        payload = json.loads(body["messages"][-1]["content"])
        if response["name"] == "CategorySelection":
            answer = {"assignments": {rack.id: key for key, rack in zip(keys, racks)}}
        else:
            assert response["name"] == "ProductSelection"
            schema = response["schema"]
            Draft202012Validator.check_schema(schema)
            validator = Draft202012Validator(schema)
            choices = {key: [p["sku"] for p in payload["categories"][key]] for key in keys}
            answer = {"selections": {key: choices[key][:1] for key in keys}}
            assert validator.is_valid(answer)
            for index, key in enumerate(keys):
                other = keys[1 - index]
                wrong = json.loads(json.dumps(answer))
                wrong["selections"][key] = [choices[other][0]]
                assert not validator.is_valid(wrong), "Cross-category SKUs must be impossible in the grammar"
                wrong["selections"][key] = ["invented-sku"]
                assert not validator.is_valid(wrong)
                wrong["selections"]["invented-category"] = wrong["selections"].pop(key)
                assert not validator.is_valid(wrong)
                maximum = min(16, limits[key], capacities[index])
                wrong["selections"][key] = [choices[key][0]] * (maximum + 1)
                assert not validator.is_valid(wrong), "Respect the actual per-category shelf capacity"
            assert not validator.is_valid({"selections": {keys[0]: choices[keys[0]][:1]}})
            assert not validator.is_valid({"selections": {**answer["selections"], "extra": choices[keys[0]][:1]}})
        return httpx.Response(200, request=request, json={"id": "offline", "object": "chat.completion", "created": 0,
            "model": body["model"], "choices": [{"index": 0, "finish_reason": "stop",
                "message": {"role": "assistant", "content": json.dumps(answer)}}]})

    async def exercise():
        async with httpx.AsyncClient(transport=httpx.MockTransport(respond)) as http:
            adapter = AsyncOpenAI(api_key="offline", base_url="http://127.0.0.1:8081/v1", http_client=http, max_retries=0)

            async def completion(**kwargs):
                return await original(**{**kwargs, "client": adapter, "api_key": "offline", "num_retries": 0})

            monkeypatch.setattr(llm_client.litellm, "acompletion", completion)
            client = llm_client.LiteLLMClient(LLMConfig(model="openai/primary-products", api_base="http://127.0.0.1:8081/v1",
                structured_output="json_schema", cache_dir=str(tmp_path)))
            first = await select_starter_products(client, store, racks, "동네 주민", allowed_categories=set(keys),
                product_limits=limits, products_per_slot=1)
            second = await select_starter_products(client, store, racks, "동네 주민", allowed_categories=set(keys),
                product_limits=limits, products_per_slot=1)
            assert first == second and client.get_usage().cached_requests == 2
            assert [row.rack_id for row in first] == [rack.id for rack in racks]
            assert [row.category for row in first] == keys

    asyncio.run(exercise())
    assert len(requests) == 2 and store.model_dump() == before
