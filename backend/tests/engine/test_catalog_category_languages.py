"""Generated category preferences must resolve on localized catalog shelves."""

import asyncio
import json
import random

import httpx
import pytest
from openai import AsyncOpenAI

from store_emulator.domain.behavior import BehaviorPattern
from store_emulator.domain.config import LLMConfig
from store_emulator.domain.types import Weekday
from store_emulator.engine import llm_client
from store_emulator.engine.generators import persona as gen
from store_emulator.engine.layout_gen.catalog import CATALOG, CATEGORY_LABELS, catalog_slot_item, category_label
from store_emulator.engine.routing.pathfinder import AStarPathFinder
from store_emulator.engine.simulation.customer_executor import execute_decision
from store_emulator.engine.simulation.engines.rule_based import RuleBasedEngine, tokenize
from store_emulator.engine.simulation.engines.vlm_glance import VLMGlanceEngine
from store_emulator.engine.simulation.engines.vlm_glance.planning import match_plan_item
from store_emulator.engine.simulation.engines.vlm_glance.prompt import PlannedItem
from tests.engine.test_llm_engine_offline import _context
from tests.engine.test_llm_impulse_exposure import fixture
from tests.engine.test_vlm_plan import _config


def catalog_store(category, currency):
    store, _ = fixture()
    store.currency = currency
    shelf = store.racks[0]
    shelf.rack_name = category_label(category, currency)
    shelf.rack_desc = category
    shelf.slots[0].items = [catalog_slot_item(CATALOG[category][0], currency)]
    return store, shelf.slots[0].items[0]


@pytest.mark.parametrize("category", ["fresh_produce", "car_care", "stationery", "souvenirs"])
@pytest.mark.parametrize("currency", ["USD", "KRW", "JPY"])
@pytest.mark.parametrize("language", [0, 1])
def test_known_catalog_labels_resolve_in_both_languages(category, currency, language):
    store, item = catalog_store(category, currency)
    engine = RuleBasedEngine(AStarPathFinder(), _config())
    query = CATEGORY_LABELS[category][language]
    picked = engine._pick_item(store, query, None, set(), random.Random(0))
    assert picked is not None and picked[2].sku == item.sku
    matched = match_plan_item(PlannedItem(category=query), engine._catalog_for(store))
    assert matched.candidates and {entry[2].sku for entry in matched.candidates} == {item.sku}


def test_custom_shelves_and_underscored_product_codes_keep_existing_matching():
    store, item = catalog_store("fresh_produce", "KRW")
    store.racks[0].rack_name = "Custom display"
    store.racks[0].rack_desc = "Special collection"
    item.name = "AB_123"
    engine = RuleBasedEngine(AStarPathFinder(), _config())
    assert not match_plan_item(PlannedItem(category="Fresh Produce"), engine._catalog_for(store)).candidates
    assert tokenize("AB_123") == {"ab_123"} and tokenize("AB_456") == {"ab_456"}
    assert match_plan_item(PlannedItem(product="AB_123"), engine._catalog_for(store)).how == "exact"


@pytest.mark.parametrize("mode", ["json", "json_schema"])
@pytest.mark.parametrize("engine_kind", ["rule", "vision"])
@pytest.mark.parametrize("currency", ["USD", "KRW", "JPY"])
@pytest.mark.parametrize("language", [0, 1])
def test_http_customer_and_vision_plans_buy_localized_catalog_products(monkeypatch, tmp_path, mode, engine_kind, currency, language):
    store, item = catalog_store("fresh_produce", currency)
    query = CATEGORY_LABELS["fresh_produce"][language]
    original, calls = llm_client.litellm.acompletion, []

    def respond(request):
        body = json.loads(request.content)
        calls.append(body)
        if "personas" in body["messages"][0]["content"]:
            answer = {"personas": [dict(identity="resident", age_group="30s", gender="Female", description="Local shopper",
                intent="Buy fresh produce", purpose="shopping", preferred_categories=[query], budget_max=10000)]}
        else:
            answer = {"mission": "Buy fresh produce", "enter": True, "items": [{"category": query, "product": "", "qty": 1}]}
        return httpx.Response(200, request=request, json={"id": "offline", "object": "chat.completion", "created": 0,
            "model": body["model"], "choices": [{"index": 0, "finish_reason": "stop",
                "message": {"role": "assistant", "content": json.dumps(answer, ensure_ascii=False)}}]})

    async def exercise():
        async with httpx.AsyncClient(transport=httpx.MockTransport(respond)) as http:
            adapter = AsyncOpenAI(api_key="offline", base_url="http://127.0.0.1:8081/v1", http_client=http, max_retries=0)

            async def completion(**kwargs):
                return await original(**{**kwargs, "client": adapter, "api_key": "offline", "num_retries": 0})

            monkeypatch.setattr(llm_client.litellm, "acompletion", completion)
            client = llm_client.LiteLLMClient(LLMConfig(model="openai/catalog-category-language", api_base="http://127.0.0.1:8081/v1",
                structured_output=mode, cache_dir=str(tmp_path)))
            config = _config(entrance_image=False, max_glances=0).model_copy(update={"budget_tolerance": None})
            config.engines.rule_based.planned_hit_prob = 1
            for repeat in range(2):
                people = await gen.generate_personas_for_day(client, "offline",
                    gen.TradeAreaProfile(keywords=[], identities=["resident"], purposes=["shopping"]), Weekday.MON,
                    [gen.HourlyProfile(hour=12, visitor_count=1, person_types=["resident"])], seed=0, currency=currency)
                assert len(people) == 1 and people[0].preferred_categories == [query]
                context = _context(store, people[0])
                context.seed = 0
                context.behavior_patterns = [BehaviorPattern(id="purposeful", name="Shop", description="", grammar="",
                    browse_required_before_buy=False, max_products=1, allow_no_purchase=False)]
                paths = AStarPathFinder()
                engine = RuleBasedEngine(paths, config) if engine_kind == "rule" else VLMGlanceEngine(client, paths, config)
                decision = await engine.decide_actions(context)
                result = execute_decision(store, people[0].id, Weekday.MON, "12:00:00", decision, paths, 1)
                assert [(buy.product_sku, buy.price) for buy in result.purchases] == [(item.sku, item.price)]
                assert result.total_spent == item.price
                expected = 1 if engine_kind == "rule" else 2
                assert len(calls) == expected and client.get_usage().cached_requests == repeat * expected

    asyncio.run(exercise())
