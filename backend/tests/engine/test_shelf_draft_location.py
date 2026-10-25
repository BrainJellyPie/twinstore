"""A repeated SKU must be tested on the shelf selected by the model."""

import asyncio
import json

import httpx
import pytest
from instructor.core.exceptions import InstructorRetryException
from openai import AsyncOpenAI

from store_emulator.domain.config import LLMConfig
from store_emulator.engine import llm_client
from store_emulator.engine.marketing.shelf_test_design import MAX_LISTED, _Draft, _listing, design_shelf_test, to_design
from tests.engine.test_scenario_target_matching import target_store


@pytest.mark.parametrize("mode", ["json", "json_schema"])
@pytest.mark.parametrize("asked", ["Drinks 10", "r10", " drinks 10 "])
@pytest.mark.parametrize("reverse", [False, True])
def test_http_repeated_product_keeps_selected_shelf_and_cached_target(monkeypatch, tmp_path, mode, asked, reverse):
    store = target_store()
    store.racks[1].slots[0].items.append(store.racks[0].slots[0].items[0].model_copy(update={"price": 249}))
    if reverse:
        store.racks.reverse()
    before = store.model_dump_json()
    payload = {"name": "Entry shelf offer", "product": "Cola 500ml", "shelf": asked, "promo": "SALE"}
    original, calls = llm_client.litellm.acompletion, []

    def respond(request):
        body = json.loads(request.content)
        calls.append(body)
        return httpx.Response(200, request=request, json={"id": "offline", "object": "chat.completion", "created": 0,
            "model": body["model"], "choices": [{"index": 0, "finish_reason": "stop",
                "message": {"role": "assistant", "content": json.dumps(payload)}}]})

    async def exercise():
        async with httpx.AsyncClient(transport=httpx.MockTransport(respond)) as http:
            adapter = AsyncOpenAI(api_key="offline", base_url="http://127.0.0.1:8081/v1", http_client=http, max_retries=0)

            async def completion(**kwargs):
                return await original(**{**kwargs, "client": adapter, "api_key": "offline", "num_retries": 0})

            monkeypatch.setattr(llm_client.litellm, "acompletion", completion)
            client = llm_client.LiteLLMClient(LLMConfig(model="openai/shelf-draft-location", api_base="http://127.0.0.1:8081/v1",
                structured_output=mode, cache_dir=str(tmp_path)))
            for repeat in range(2):
                result = await design_shelf_test(client, "Test a SALE sign on Cola 500ml at Drinks 10", store, "USD", [])
                assert result.rack_id == "r10" and result.target_sku == "s-cola"
                assert len(result.changes) == 1 and result.changes[0].promo == "SALE" and not result.warnings
                user = calls[0]["messages"][1]["content"]
                products = user.split("\n", 1)[0].removeprefix("Products: ").split("; ")
                assert any(product.startswith("Cola 500ml ($2.49, Drinks 10") for product in products)
                assert any(product.startswith("Cola 500ml ($1.00, Drinks 1,") for product in products)
                assert len(calls) == 1 and client.get_usage().cached_requests == repeat
                assert store.model_dump_json() == before

    asyncio.run(exercise())


@pytest.mark.parametrize("mode", ["json", "json_schema"])
@pytest.mark.parametrize("failure", ["unknown", "wrong_product", "ambiguous"])
def test_invalid_shelf_retries_without_cache_or_silent_retargeting(monkeypatch, tmp_path, mode, failure):
    store = target_store()
    shelf = "Unknown shelf" if failure == "unknown" else "Drinks 10"
    if failure == "ambiguous":
        store.racks[1].slots[0].items.append(store.racks[0].slots[0].items[0].model_copy())
        store.racks[0].rack_name = store.racks[1].rack_name = "Drinks 10"
    payload = {"name": "Location test", "product": "Cola 500ml", "shelf": shelf, "promo": "SALE"}
    original, calls = llm_client.litellm.acompletion, []
    healthy = False

    def respond(request):
        body = json.loads(request.content)
        calls.append(body)
        answer = {**payload, "shelf": "r1"} if healthy else payload
        return httpx.Response(200, request=request, json={"id": "offline", "object": "chat.completion", "created": 0,
            "model": body["model"], "choices": [{"index": 0, "finish_reason": "stop",
                "message": {"role": "assistant", "content": json.dumps(answer)}}]})

    async def exercise():
        nonlocal healthy
        async with httpx.AsyncClient(transport=httpx.MockTransport(respond)) as http:
            adapter = AsyncOpenAI(api_key="offline", base_url="http://127.0.0.1:8081/v1", http_client=http, max_retries=0)

            async def completion(**kwargs):
                return await original(**{**kwargs, "client": adapter, "api_key": "offline", "num_retries": 0})

            monkeypatch.setattr(llm_client.litellm, "acompletion", completion)
            client = llm_client.LiteLLMClient(LLMConfig(model="openai/shelf-draft-invalid-location", api_base="http://127.0.0.1:8081/v1",
                structured_output=mode, cache_dir=str(tmp_path)))

            async def draft():
                return await design_shelf_test(client, "Test SALE on the requested Cola shelf", store, "USD", [])

            with pytest.raises(InstructorRetryException):
                await draft()
            assert len(calls) == 2 and not list(tmp_path.rglob("*.json"))
            healthy = True
            result = await draft()
            assert result.rack_id == "r1" and result.target_sku == "s-cola"
            assert await draft() == result and len(calls) == 3

    asyncio.run(exercise())


@pytest.mark.parametrize("shelf", [None, "", "   "])
def test_unspecified_shelf_keeps_existing_first_placement_default(shelf):
    store = target_store()
    result = to_design(_Draft.model_validate({"name": "Test", "product": "Cola 500ml", "shelf": shelf, "promo": "SALE"}),
                       store, "USD", [])
    assert result.rack_id == "r1"


@pytest.mark.parametrize("prefix", [False, True])
def test_long_shelf_name_resolves_only_a_unique_prefix(prefix):
    store = target_store()
    store.racks[1].slots[0].items.append(store.racks[0].slots[0].items[0].model_copy())
    name = "Entrance tea section " + "A" * 150
    store.racks[1].rack_name = name
    draft = _Draft(name="Test", product="Cola 500ml", shelf=name[:160] if prefix else "r10", promo="SALE")
    assert to_design(draft, store, "USD", []).rack_id == "r10"
    if prefix:
        store.racks[0].rack_name = name[:160] + " another shelf"
        with pytest.raises(ValueError, match="does not uniquely identify"):
            to_design(draft, store, "USD", [])


def test_explicit_shelf_id_survives_a_large_repeated_product_listing():
    store = target_store()
    rack = store.racks[0]
    rack.slots[0].items = rack.slots[0].items[:1]
    store.racks = [rack.model_copy(deep=True, update={"id": f"rack_{i}", "rack_name": f"Shelf {i}",
                    "position": (i % 20 * 2 + 1, i // 20 * 2 + 1)}) for i in range(MAX_LISTED + 1)]
    store.grid_size = (50, 50)
    text = _listing(store, "USD", [], f"Test Cola 500ml on rack_{MAX_LISTED}")
    products = text.split("\n", 1)[0].removeprefix("Products: ").split("; ")
    assert len(products) == MAX_LISTED
    assert f"ID rack_{MAX_LISTED})" in products[0]
