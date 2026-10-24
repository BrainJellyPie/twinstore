"""Null optional prose must not discard an otherwise valid shopping decision."""

import asyncio
import json

import httpx
import pytest
from openai import AsyncOpenAI
from pydantic import ValidationError

from store_emulator.domain.config import LLMConfig, SimulationConfig
from store_emulator.domain.types import Action, Weekday
from store_emulator.engine import llm_client
from store_emulator.engine.routing.pathfinder import AStarPathFinder
from store_emulator.engine.simulation.customer_executor import execute_decision
from store_emulator.engine.simulation.engines.pattern_intent_impulse.engine import PatternIntentImpulseEngine
from store_emulator.engine.simulation.engines.pattern_intent_impulse.stage1_pattern import PatternSelectionResponse
from store_emulator.engine.simulation.engines.pattern_intent_impulse.stage2_intent import IntentResponse
from store_emulator.engine.simulation.engines.pattern_intent_impulse.stage3_impulse import ImpulseResponse
from tests.engine.test_llm_engine_offline import _context, _intent, _persona


@pytest.mark.parametrize("mode", ["json", "json_schema"])
@pytest.mark.parametrize("null_field", ["pattern_reason", "override", "intent_reason", "intent_description", "impulse_reason", "impulse_description"])
def test_http_null_narration_keeps_the_complete_visit_and_can_be_reused_from_cache(monkeypatch, tmp_path, collision_store, mode, null_field):
    original = llm_client.litellm.acompletion
    calls = []

    def respond(request):
        body = json.loads(request.content)
        calls.append(body)
        if len(calls) == 1:
            answer = {"pattern_id": "exploratory"}
            if null_field == "pattern_reason":
                answer["reasoning"] = None
            if null_field == "override":
                answer["grammar_override"] = None
        elif len(calls) == 2:
            answer = _intent().model_dump(mode="json")
            if null_field == "intent_reason":
                answer["reasoning"] = None
            if null_field == "intent_description":
                for action in answer["actions"]:
                    action["description"] = None
        else:
            assert len(calls) == 3
            answer = {"actions": [{"nav": "path", "action": "buy", "product_sku": "sku-b", "quantity": 1,
                                   "target": [1, 0], "face": "W"}]}
            if null_field == "impulse_reason":
                answer["reasoning"] = None
            if null_field == "impulse_description":
                answer["actions"][0]["description"] = None
        return httpx.Response(200, request=request, json={"id": "offline", "object": "chat.completion", "created": 0,
            "model": body["model"], "choices": [{"index": 0, "finish_reason": "stop",
                "message": {"role": "assistant", "content": json.dumps(answer)}}]})

    async def exercise():
        async with httpx.AsyncClient(transport=httpx.MockTransport(respond)) as http:
            transport = AsyncOpenAI(api_key="offline", base_url="http://127.0.0.1:8081/v1", http_client=http, max_retries=0)

            async def completion(**kwargs):
                return await original(**{**kwargs, "client": transport, "api_key": "offline", "num_retries": 0})

            monkeypatch.setattr(llm_client.litellm, "acompletion", completion)
            client = llm_client.LiteLLMClient(LLMConfig(model="openai/local-optional-prose", api_base="http://127.0.0.1:8081/v1",
                structured_output=mode, cache_dir=str(tmp_path)))
            engine = PatternIntentImpulseEngine(client, AStarPathFinder(), SimulationConfig())
            first = await engine.decide_actions(_context(collision_store, _persona()))
            # Legacy or externally supplied cached null prose uses the same boundary.
            for path in tmp_path.glob("*/*.json"):
                saved = json.loads(path.read_text())
                saved["result"]["reasoning"] = None
                if "grammar_override" in saved["result"]:
                    saved["result"]["grammar_override"] = None
                for action in saved["result"].get("actions", []):
                    action["description"] = None
                path.write_text(json.dumps(saved))
            second = await engine.decide_actions(_context(collision_store, _persona()))
            assert first == second and client.get_usage().cached_requests == 3
            assert all(first.trace[stage]["reasoning"] == "" for stage in ["stage1", "stage2", "stage3"])
            assert first.trace["stage1"]["grammar_override"] == ""
            result = execute_decision(collision_store, "P1", Weekday.MON, "12:00:00", first, AStarPathFinder(), 1)
            assert result.total_spent == 500 and result.timeline[-1].action == Action.EXIT

    asyncio.run(exercise())
    assert len(calls) == 3


@pytest.mark.parametrize("schema", [PatternSelectionResponse, IntentResponse, ImpulseResponse])
@pytest.mark.parametrize("bad", [[], {}, 7, False])
def test_invalid_prose_types_are_still_rejected(schema, bad):
    with pytest.raises(ValidationError):
        schema.model_validate_json(json.dumps({"reasoning": bad}), strict=True)


@pytest.mark.parametrize("schema", [IntentResponse, ImpulseResponse])
@pytest.mark.parametrize("field", ["nav", "quantity", "product_sku"])
def test_null_structural_fields_are_still_rejected(schema, field):
    action = {"nav": "path", "action": "buy", "quantity": 1, "product_sku": "tea", field: None}
    with pytest.raises(ValidationError):
        schema.model_validate_json(json.dumps({"actions": [action]}), strict=True)
