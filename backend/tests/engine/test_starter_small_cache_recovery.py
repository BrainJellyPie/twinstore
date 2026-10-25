"""A failed small catalog task must not poison every later attempt through cached invalid choices."""

import asyncio
import json

import httpx
import pytest
from openai import AsyncOpenAI

from store_emulator.domain.config import LLMConfig
from store_emulator.domain.starter_fill import StarterRack
from store_emulator.engine import llm_client
from store_emulator.engine.layout_gen.catalog import CATALOG, catalog_slot_item
from store_emulator.engine.starter_fill import fill_empty_racks
from store_emulator.engine.starter_selection import select_starter_products
from tests.engine.test_starter_selection import empty_store


@pytest.mark.parametrize("mode", ["json", "json_schema"])
@pytest.mark.parametrize("fault", ["unknown_category", "unknown_sku", "duplicate_sku"])
@pytest.mark.parametrize("old_cache", [False, True])
def test_a_failed_fill_can_retry_after_the_model_improves(monkeypatch, tmp_path, mode, fault, old_cache):
    store = empty_store()
    before = store.model_dump()
    racks = [StarterRack(id="a", name="Tea", type="shelf", available_slots=4)]
    category = "home_coffee_tea"
    skus = [catalog_slot_item(product, "USD").sku for product in CATALOG[category]][:2]
    original, calls, recovered = llm_client.litellm.acompletion, [], False

    def respond(request):
        body = json.loads(request.content)
        calls.append(body)
        context = json.loads(next(message["content"] for message in body["messages"] if message["role"] == "user"))
        if "expected_rack_ids" in context:
            answer = {"groups": [{"category": category,
                                  "rack_ids": ["invented-rack"] if fault == "unknown_category" else ["a"]}]}
        elif "racks" in context:
            answer = {"choices": [category if recovered else "invented-category"]}
        elif "Choose products for the ONE supplied category." in body["messages"][0]["content"]:
            answer = {"choices": skus if recovered else [skus[0], skus[0]] if fault == "duplicate_sku" else ["invented-sku"]}
        else:
            answer = {"groups": [{"category": category, "skus": skus if fault == "unknown_category" else ["invented-sku"]}]}
        return httpx.Response(200, request=request, json={"id": "offline", "object": "chat.completion", "created": 0,
            "model": body["model"], "choices": [{"index": 0, "finish_reason": "stop",
                "message": {"role": "assistant", "content": json.dumps(answer)}}]})

    async def exercise():
        nonlocal recovered
        async with httpx.AsyncClient(transport=httpx.MockTransport(respond)) as http:
            adapter = AsyncOpenAI(api_key="offline", base_url="http://127.0.0.1:8081/v1", http_client=http, max_retries=0)

            async def completion(**kwargs):
                return await original(**{**kwargs, "client": adapter, "api_key": "offline", "num_retries": 0})

            monkeypatch.setattr(llm_client.litellm, "acompletion", completion)
            client = llm_client.LiteLLMClient(LLMConfig(model="openai/starter-cache-recovery",
                api_base="http://127.0.0.1:8081/v1", structured_output=mode, cache_dir=str(tmp_path)))
            generate, seeded = client.generate_structured_async, False

            async def generate_with_old_cache(schema, system, user, **kwargs):
                nonlocal seeded
                if old_cache and recovered and not seeded and "choices" in schema.model_fields:
                    path = client._cache_path(schema, client._messages(system, user)[0], kwargs.get("seed"))
                    path.parent.mkdir(parents=True, exist_ok=True)
                    invalid = [skus[0], skus[0]] if fault == "duplicate_sku" else ["invented"]
                    path.write_text(json.dumps({"result": {"choices": invalid}}))
                    seeded = True
                return await generate(schema, system, user, **kwargs)

            monkeypatch.setattr(client, "generate_structured_async", generate_with_old_cache)

            async def select():
                return await select_starter_products(client, store, racks, "Tea for local residents",
                    allowed_categories={category}, product_limits={category: 2})

            with pytest.raises(ValueError):
                await select()
            assert store.model_dump() == before
            assert not any("choices" in json.loads(path.read_text())["result"] for path in tmp_path.rglob("*.json"))
            failed_calls = len(calls)
            recovered = True
            choices = await select()
            assert len(calls) > failed_calls, "Retry must reach the provider instead of replaying an invalid cache"
            assert len(choices) == 1 and choices[0].rack_id == "a" and choices[0].skus == skus
            filled, report = fill_empty_racks(store, choices, 2)
            assert {item.sku for rack in filled.racks for slot in rack.slots for item in slot.items} == set(skus)
            assert report.racks and store.model_dump() == before
            successful_calls = len(calls)
            assert await select() == choices and len(calls) == successful_calls
            assert seeded == old_cache
            small_cached = [data["result"]["choices"] for path in tmp_path.rglob("*.json")
                            if "choices" in (data := json.loads(path.read_text()))["result"]]
            assert small_cached and all(values in ([category], skus) for values in small_cached)

    asyncio.run(exercise())
