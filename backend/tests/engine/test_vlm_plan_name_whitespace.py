"""Padded catalog names must not redirect a model's plan to another category."""

import asyncio
import json

import httpx
import pytest
from openai import AsyncOpenAI

from store_emulator.domain.config import LLMConfig
from store_emulator.domain.types import Weekday
from store_emulator.engine import llm_client
from store_emulator.engine.routing.pathfinder import AStarPathFinder
from store_emulator.engine.simulation.customer_executor import execute_decision
from store_emulator.engine.simulation.engines.vlm_glance import VLMGlanceEngine
from store_emulator.engine.simulation.engines.vlm_glance.planning import match_plan_item
from store_emulator.engine.simulation.engines.vlm_glance.prompt import PLAN_PRODUCT_LIMIT, PlannedItem
from tests.engine.test_purchase_quantity_limits import context_for
from tests.engine.test_vlm_plan import _config
from tests.engine.test_vlm_plan_category_disambiguation import fixture


@pytest.mark.parametrize("mode", ["json", "json_schema"])
@pytest.mark.parametrize("same_sku", [False, True])
@pytest.mark.parametrize("reverse", [False, True])
@pytest.mark.parametrize("name", ["Original", "X", "茶", "Straße"])
@pytest.mark.parametrize("padding", [" ", "\u3000\t"])
def test_http_plan_buys_the_named_offer_despite_stored_name_padding(monkeypatch, tmp_path,
                                                                 mode, same_sku, reverse, name, padding):
    store, _ = fixture(same_sku, reverse, name)
    next(r for r in store.racks if r.id == "milk").slots[0].items[0].name = padding + name + padding
    before = store.model_dump_json()
    original, calls = llm_client.litellm.acompletion, []
    payload = {"enter": True, "items": [{"category": " mIlK ", "product": name.upper(), "qty": 1}]}

    def respond(request):
        body = json.loads(request.content)
        calls.append(body)
        return httpx.Response(200, request=request, json={"id": "offline", "object": "chat.completion", "created": 0,
            "model": body["model"], "choices": [{"index": 0, "finish_reason": "stop", "message": {
                "role": "assistant", "content": json.dumps(payload)}}]})

    async def exercise():
        async with httpx.AsyncClient(transport=httpx.MockTransport(respond)) as http:
            adapter = AsyncOpenAI(api_key="offline", base_url="http://127.0.0.1:8081/v1", http_client=http, max_retries=0)

            async def completion(**kwargs):
                return await original(**{**kwargs, "client": adapter, "api_key": "offline", "num_retries": 0})

            monkeypatch.setattr(llm_client.litellm, "acompletion", completion)
            client = llm_client.LiteLLMClient(LLMConfig(model="openai/vlm-plan-name-whitespace",
                api_base="http://127.0.0.1:8081/v1", structured_output=mode, cache_dir=str(tmp_path)))
            paths = AStarPathFinder()
            engine = VLMGlanceEngine(client, paths, _config(entrance_image=False, max_glances=0).model_copy(
                update={"budget_tolerance": None}))
            for repeat in range(2):
                decision = await engine.decide_actions(context_for(store, 13))
                result = execute_decision(store, "shopper", Weekday.MON, "12:00:00", decision, paths, 1)
                assert len(result.purchases) == 1
                buy = result.purchases[0]
                assert (buy.target_rack, buy.product_sku, buy.price, buy.product_level, buy.quantity) == (
                    "milk", "shared" if same_sku else "milk", 700, 3, 1)
                assert result.total_spent == 700
                assert engine.plan_log[-1].resolved[0][2:4] == ("exact", "Milk")
                assert len(calls) == 1 and client.get_usage().cached_requests == repeat
            assert store.model_dump_json() == before

    asyncio.run(exercise())


@pytest.mark.parametrize("same_sku", [False, True])
@pytest.mark.parametrize("reverse", [False, True])
@pytest.mark.parametrize("padding", [" ", "\u3000\t"])
def test_clipped_names_keep_the_named_category_before_global_prefix_matches(same_sku, reverse, padding):
    name = "Original milk with a long printed product description and package size"
    store, engine = fixture(same_sku, reverse, name)
    next(r for r in store.racks if r.id == "milk").slots[0].items[0].name = padding + name + padding
    match = match_plan_item(PlannedItem(category="Milk", product=name[:PLAN_PRODUCT_LIMIT]), engine._catalog_for(store))
    assert match.how == "prefix" and {e[0].id for e in match.candidates} == {"milk"}


@pytest.mark.parametrize("category", ["", "Unknown"])
def test_unqualified_equal_names_keep_all_offers_instead_of_guessing(category):
    store, engine = fixture(False, False)
    next(r for r in store.racks if r.id == "milk").slots[0].items[0].name = " Original "
    match = match_plan_item(PlannedItem(category=category, product="Original"), engine._catalog_for(store))
    assert match.how == "exact" and {e[2].sku for e in match.candidates} == {"milk", "snacks"}


def test_internal_whitespace_does_not_merge_distinct_catalog_names():
    store, engine = fixture(False, False, "Green Tea")
    next(r for r in store.racks if r.id == "milk").slots[0].items[0].name = " Green  Tea "
    match = match_plan_item(PlannedItem(category="Milk", product="Green Tea"), engine._catalog_for(store))
    assert match.how == "exact" and {e[0].id for e in match.candidates} == {"snacks"}
