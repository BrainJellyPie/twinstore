"""Human-readable target labels must retain exact scope despite surrounding whitespace."""

import asyncio
import json

import httpx
import pytest
from openai import AsyncOpenAI

from store_emulator.domain.config import LLMConfig
from store_emulator.domain.scenario import Promotion, Scenario
from store_emulator.engine import llm_client
from store_emulator.engine.scenario import apply_to_store
from store_emulator.engine.scenario_writer import describe_scenario
from tests.engine.test_scenario_target_matching import target_store


@pytest.mark.parametrize("mode", ["json", "json_schema"])
@pytest.mark.parametrize("operation", ["promotion", "stockout"])
@pytest.mark.parametrize("target_kind", ["product", "shelf", "category"])
@pytest.mark.parametrize("padding", [" ", "\t\n", "\u3000\u00a0"])
def test_generated_target_does_not_expand_because_source_name_has_whitespace(monkeypatch, tmp_path, mode, operation, target_kind, padding):
    store = target_store()
    expected = {"s-cola"} if target_kind == "product" else {"s-cola", "s-zero", "s-lemon", "s-large"}
    if target_kind == "product":
        target = "Cola 500ml"
        store.racks[0].slots[0].items[0].name = padding + target + padding
    elif target_kind == "shelf":
        target = "Drinks 1"
        store.racks[0].rack_name = padding + target + padding
    else:
        target = "seasonal specials"
        store.racks[0].rack_desc = padding + target + padding
        store.racks[1].rack_desc = "seasonal extras"
    before = store.model_dump_json()
    original, calls = llm_client.litellm.acompletion, []

    def respond(request):
        body = json.loads(request.content)
        calls.append(body)
        payload = {"name": "Trading day"}
        if operation == "promotion":
            payload["promotions"] = [{"target": target.upper(), "discount_pct": 50}]
        else:
            payload["stockouts"] = [target.upper()]
        return httpx.Response(200, request=request, json={"id": "offline", "object": "chat.completion", "created": 0,
            "model": body["model"], "choices": [{"index": 0, "finish_reason": "stop",
                "message": {"role": "assistant", "content": json.dumps(payload)}}]})

    async def exercise():
        async with httpx.AsyncClient(transport=httpx.MockTransport(respond)) as http:
            adapter = AsyncOpenAI(api_key="offline", base_url="http://127.0.0.1:8081/v1", http_client=http, max_retries=0)

            async def completion(**kwargs):
                return await original(**{**kwargs, "client": adapter, "api_key": "offline", "num_retries": 0})

            monkeypatch.setattr(llm_client.litellm, "acompletion", completion)
            client = llm_client.LiteLLMClient(LLMConfig(model="openai/scenario-whitespace", api_base="http://127.0.0.1:8081/v1",
                structured_output=mode, cache_dir=str(tmp_path)))
            result = await describe_scenario(client, f"Apply only to {target}", store)
            changed, lifts = apply_to_store(store, result.scenario)
            items = {item.sku: item for rack in changed.racks for slot in rack.slots for item in slot.items}
            original_skus = {item.sku for rack in store.racks for slot in rack.slots for item in slot.items}
            affected = {sku for sku, item in items.items() if item.price == 50} if operation == "promotion" else original_skus - items.keys()
            assert affected == expected
            assert set(lifts) == (expected if operation == "promotion" else set())
            assert "s-beer" in items and items["s-beer"].price == 100
            assert store.model_dump_json() == before
            assert await describe_scenario(client, f"Apply only to {target}", store) == result
            assert len(calls) == 1 and client.get_usage().cached_requests == 1
            if target_kind == "product":
                assert not result.warnings

    asyncio.run(exercise())


@pytest.mark.parametrize("target_kind", ["product", "shelf"])
def test_padded_long_names_restore_to_one_canonical_label_before_matching(target_kind):
    from store_emulator.engine.scenario_writer import ScenarioDraft, to_scenario

    store = target_store()
    prefix = ("Premium " + "Special Cola selection " * 10)[:80]
    full = prefix + " original 500 ml"
    if target_kind == "product":
        store.racks[0].slots[0].items[0].name = "\u3000" + full + "\t"
        expected = {"s-cola"}
    else:
        store.racks[0].rack_name = "\u3000" + full + "\t"
        expected = {"s-cola", "s-zero", "s-lemon", "s-large"}
    result = to_scenario(ScenarioDraft(name="Day", promotions=[{"target": prefix, "discount_pct": 50}]), "Promotion", store)
    assert result.scenario.promotions[0].target == full
    _, lifts = apply_to_store(store, result.scenario)
    assert set(lifts) == expected


@pytest.mark.parametrize("operation", ["promotion", "stockout"])
def test_duplicate_normalized_names_keep_their_shared_scope(operation):
    store = target_store()
    store.racks[0].slots[0].items[0].name = " Cola 500ml "
    store.racks[0].slots[0].items[1].name = "\u3000Cola 500ml\t"
    scenario = Scenario(promotions=[Promotion(target="Cola 500ml", discount_pct=50)]) if operation == "promotion" else Scenario(stockouts=["Cola 500ml"])
    changed, lifts = apply_to_store(store, scenario)
    items = {i.sku: i for r in changed.racks for s in r.slots for i in s.items}
    assert set(lifts) == ({"s-cola", "s-zero"} if operation == "promotion" else set())
    assert {"s-lemon", "s-large", "s-beer"} <= items.keys()
    assert all(items[sku].price == 100 for sku in ["s-lemon", "s-large", "s-beer"])
    if operation == "stockout":
        assert {"s-cola", "s-zero"}.isdisjoint(items)
