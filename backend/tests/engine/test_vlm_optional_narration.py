"""Absent optional vision-model text must not discard otherwise valid choices."""

import asyncio
import json

import httpx
import pytest
from openai import AsyncOpenAI
from pydantic import ValidationError

from store_emulator.domain.config import LLMConfig, SimulationConfig
from store_emulator.domain.types import Weekday
from store_emulator.engine import llm_client
from store_emulator.engine.routing.pathfinder import AStarPathFinder
from store_emulator.engine.simulation.customer_executor import execute_decision
from store_emulator.engine.simulation.engines.vlm_glance import VLMGlanceEngine
from store_emulator.engine.simulation.engines.vlm_glance.prompt import EntryDecision, PlannedItem, ShelfGlance, resolve
from tests.engine.test_llm_engine_offline import _context, _persona
from tests.engine.test_purchase_quantity_limits import context_for
from tests.engine.test_shelf_panel_boundaries import shelf
from tests.engine.test_vlm_plan_category_disambiguation import fixture


@pytest.mark.parametrize("mode", ["json", "json_schema"])
@pytest.mark.parametrize("image", [False, True])
@pytest.mark.parametrize("field", ["mission", "reason", "category", "product"])
def test_null_entry_text_keeps_model_plan_purchase_and_cache(monkeypatch, tmp_path, mode, image, field):
    store, engine = fixture(False, False)
    store.racks[0].slots[0].items[0].name = "Different product"
    engine._config.engines.vlm_glance.entrance_image = image
    original = llm_client.litellm.acompletion
    calls = []
    answer = {"enter": True, "mission": "Buy milk", "reason": "Need milk", "items": [
        {"category": "Milk", "product": "Original", "qty": 2}]}
    (answer["items"][0] if field in {"category", "product"} else answer)[field] = None

    def respond(request):
        body = json.loads(request.content)
        calls.append(body)
        return httpx.Response(200, request=request, json={"id": "offline", "object": "chat.completion", "created": 0,
            "model": body["model"], "choices": [{"index": 0, "finish_reason": "stop",
                "message": {"role": "assistant", "content": json.dumps(answer)}}]})

    async def exercise():
        async with httpx.AsyncClient(transport=httpx.MockTransport(respond)) as http:
            adapter = AsyncOpenAI(api_key="offline", base_url="http://127.0.0.1:8081/v1", http_client=http, max_retries=0)

            async def completion(**kwargs):
                return await original(**{**kwargs, "client": adapter, "api_key": "offline", "num_retries": 0})

            monkeypatch.setattr(llm_client.litellm, "acompletion", completion)
            client = llm_client.LiteLLMClient(LLMConfig(model="openai/null-vision", api_base="http://127.0.0.1:8081/v1",
                structured_output=mode, cache_dir=str(tmp_path)))
            engine._llm = client
            first = await engine.decide_actions(context_for(store, 0))
            second = await engine.decide_actions(context_for(store, 0))
            assert first == second and client.get_usage().cached_requests == 1
            result = execute_decision(store, "shopper", Weekday.MON, "12:00:00", first, AStarPathFinder(), 1)
            assert result.total_spent == 1400 and result.purchases[0].product_sku == "milk"
            assert result.purchases[0].quantity == 2 and first.trace["plan_source"] == "vlm"

    asyncio.run(exercise())
    assert len(calls) == 1


@pytest.mark.parametrize("mode", ["json", "json_schema"])
@pytest.mark.parametrize("field", ["product", "reason"])
def test_null_glance_text_keeps_a_visible_badge_choice(monkeypatch, tmp_path, collision_store, shelf, mode, field):
    rack, view = shelf
    original = llm_client.litellm.acompletion
    calls = []
    answer = {"product": "Banana", "number": 2, "interest": 8, "reason": "Looks good", field: None}

    def respond(request):
        body = json.loads(request.content)
        calls.append(body)
        return httpx.Response(200, request=request, json={"id": "offline", "object": "chat.completion", "created": 0,
            "model": body["model"], "choices": [{"index": 0, "finish_reason": "stop",
                "message": {"role": "assistant", "content": json.dumps(answer)}}]})

    async def exercise():
        async with httpx.AsyncClient(transport=httpx.MockTransport(respond)) as http:
            adapter = AsyncOpenAI(api_key="offline", base_url="http://127.0.0.1:8081/v1", http_client=http, max_retries=0)

            async def completion(**kwargs):
                return await original(**{**kwargs, "client": adapter, "api_key": "offline", "num_retries": 0})

            monkeypatch.setattr(llm_client.litellm, "acompletion", completion)
            client = llm_client.LiteLLMClient(LLMConfig(model="openai/null-vision", api_base="http://127.0.0.1:8081/v1",
                structured_output=mode, cache_dir=str(tmp_path)))
            engine = VLMGlanceEngine(client, AStarPathFinder(), SimulationConfig())
            args = (view, "Choose", _context(collision_store, _persona()), rack, "N")
            first = await engine._ask(*args)
            assert first == await engine._ask(*args) and client.get_usage().cached_requests == 1
            assert first[0] is not None and not first[-1]
            selected, _ = resolve(view, first[0])
            assert selected.item.sku == "B" and first[0].interest == 8
            assert getattr(first[0], field) == ""

    asyncio.run(exercise())
    assert len(calls) == 1


@pytest.mark.parametrize("schema,field", [(EntryDecision, "mission"), (EntryDecision, "reason"),
    (PlannedItem, "category"), (PlannedItem, "product"), (ShelfGlance, "product"), (ShelfGlance, "reason")])
@pytest.mark.parametrize("value", [17, [], {}])
def test_non_text_values_are_still_invalid(schema, field, value):
    with pytest.raises(ValidationError):
        schema.model_validate_json(json.dumps({field: value}), strict=True)


@pytest.mark.parametrize("schema,field", [(EntryDecision, "enter"), (EntryDecision, "items"),
    (PlannedItem, "qty"), (ShelfGlance, "number"), (ShelfGlance, "interest")])
def test_structural_nulls_are_not_guessed(schema, field):
    with pytest.raises(ValidationError):
        schema.model_validate_json(json.dumps({field: None}), strict=True)
