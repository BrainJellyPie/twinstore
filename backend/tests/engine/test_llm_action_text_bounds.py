"""Repeated action narration cannot inflate the subsequent impulse prompt."""

import asyncio
import json

import pytest

from store_emulator.domain.action import CustomerAction
from store_emulator.domain.config import SimulationConfig
from store_emulator.domain.types import Action, Weekday
from store_emulator.engine.routing.pathfinder import AStarPathFinder
from store_emulator.engine.simulation.customer_executor import execute_decision
from store_emulator.engine.simulation.engines.pattern_intent_impulse.engine import PatternIntentImpulseEngine
from store_emulator.engine.simulation.engines.pattern_intent_impulse.stage2_intent import IntentResponse
from store_emulator.engine.simulation.engines.pattern_intent_impulse.stage3_impulse import ImpulseResponse
from tests.engine.test_llm_engine_offline import _ScriptedLLM, _context, _intent, _persona


@pytest.mark.parametrize("text", ["The shopper browses the shelf. " * 2000, "고객이 진열대를 살펴봅니다. " * 2000, "🛒" * 10000])
@pytest.mark.parametrize("ordering", ["planned", "nearest"])
def test_repeated_model_action_text_stays_bounded_before_the_next_stage(collision_store, text, ordering):
    raw = _intent().model_dump()
    raw["reasoning"] = text
    for action in raw["actions"]:
        action["description"] = text

    class Model(_ScriptedLLM):
        async def generate_structured_async(self, schema, system, user, **kwargs):
            if schema is ImpulseResponse:
                assert len(system) + len(user) < 6000
            return await super().generate_structured_async(schema, system, user, **kwargs)

    model = Model(IntentResponse.model_validate(raw), ImpulseResponse())
    engine = PatternIntentImpulseEngine(model, AStarPathFinder(), SimulationConfig(route_ordering=ordering))
    decision = asyncio.run(engine.decide_actions(_context(collision_store, _persona())))
    result = execute_decision(collision_store, "P1", Weekday.MON, "12:00:00", decision, AStarPathFinder(), 1)
    assert len(model.calls) == 3 and result.total_spent == 300
    assert result.timeline[-1].action == Action.EXIT
    assert len(decision.trace["stage2"]["reasoning"]) == 600
    assert all(action["description"] == text[:400] for action in decision.trace["stage2"]["actions"])


@pytest.mark.parametrize("schema", [IntentResponse, ImpulseResponse])
@pytest.mark.parametrize("character", ["x", "한", "🛒"])
@pytest.mark.parametrize("length", [0, 399, 400, 401, 601])
def test_bounds_preserve_unicode_and_structural_action_fields(schema, character, length):
    text = character * length
    raw = {"reasoning": text, "actions": [{"nav": "path", "action": "buy", "target": [1, 2],
        "face": "S", "product_sku": "long-exact-sku-" * 50, "quantity": 3, "description": text},
        {"nav": "area", "area": [0, 1, 2, 3], "description": text}]}
    response = schema.model_validate_json(json.dumps(raw), strict=True)
    assert response.reasoning == text[:600]
    assert all(action.description == text[:400] for action in response.actions)
    assert response.actions[0].product_sku == raw["actions"][0]["product_sku"]
    assert response.actions[0].quantity == 3 and response.actions[0].target == (1, 2)
    assert response.actions[1].area == (0, 1, 2, 3)
    assert raw["actions"][0]["description"] == text


def test_domain_actions_keep_authored_narration():
    text = "authored narrative " * 100
    action = CustomerAction(nav="path", description=text, product_block=1, product_level=3)
    response = IntentResponse(actions=[action])
    assert action.description == text and action.product_level == 3
    assert response.actions[0].description == text[:400]
    assert response.actions[0].product_level is None


@pytest.mark.parametrize("schema", [IntentResponse, ImpulseResponse])
def test_grammar_bounds_model_prose_without_shortening_catalog_identifiers(schema):
    data = schema.model_json_schema()
    action = data["$defs"][data["properties"]["actions"]["items"]["$ref"].rsplit("/", 1)[-1]]["properties"]
    assert data["properties"]["reasoning"]["maxLength"] == 600
    assert action["description"]["maxLength"] == 400
    assert "maxLength" not in action["product_sku"]


@pytest.mark.parametrize("mode", ["json", "json_schema"])
def test_http_action_repetition_is_normalized_before_prompt_and_cache(monkeypatch, tmp_path, collision_store, mode):
    import httpx
    from openai import AsyncOpenAI

    from store_emulator.domain.config import LLMConfig
    from store_emulator.engine import llm_client

    calls = []
    original = llm_client.litellm.acompletion
    text = "The shopper browses the shelf. " * 2000

    def respond(request):
        body = json.loads(request.content)
        calls.append(body)
        if len(calls) == 1:
            answer = {"pattern_id": "exploratory"}
        elif len(calls) == 2:
            answer = _intent().model_dump(mode="json")
            answer["reasoning"] = text
            for action in answer["actions"]:
                action["description"] = text
        else:
            assert len(calls) == 3
            assert sum(len(m["content"]) for m in body["messages"]) < 8000
            answer = {"reasoning": text, "actions": []}
        return httpx.Response(200, request=request, json={"id": "offline", "object": "chat.completion", "created": 0,
            "model": body["model"], "choices": [{"index": 0, "finish_reason": "stop",
                "message": {"role": "assistant", "content": json.dumps(answer)}}]})

    async def exercise():
        async with httpx.AsyncClient(transport=httpx.MockTransport(respond)) as http:
            transport = AsyncOpenAI(api_key="offline", base_url="http://local.invalid/v1", http_client=http, max_retries=0)

            async def completion(**kwargs):
                return await original(**{**kwargs, "client": transport, "api_key": "offline", "num_retries": 0})

            monkeypatch.setattr(llm_client.litellm, "acompletion", completion)
            client = llm_client.LiteLLMClient(LLMConfig(model="openai/local-action-prose", api_base="http://local.invalid/v1",
                structured_output=mode, cache_dir=str(tmp_path)))
            engine = PatternIntentImpulseEngine(client, AStarPathFinder(), SimulationConfig())
            first = await engine.decide_actions(_context(collision_store, _persona()))
            second = await engine.decide_actions(_context(collision_store, _persona()))
            assert first == second and client.get_usage().cached_requests == 3
            assert len(first.trace["stage2"]["reasoning"]) == len(first.trace["stage3"]["reasoning"]) == 600

    asyncio.run(exercise())
    assert len(calls) == 3
