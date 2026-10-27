"""A repetitive optional pattern rewrite must not overflow the next model request."""

import asyncio

import pytest

from store_emulator.domain.config import SimulationConfig
from store_emulator.domain.types import Action, Weekday
from store_emulator.engine.routing.pathfinder import AStarPathFinder
from store_emulator.engine.simulation.customer_executor import execute_decision
from store_emulator.engine.simulation.engines.pattern_intent_impulse.engine import PatternIntentImpulseEngine
from store_emulator.engine.simulation.engines.pattern_intent_impulse.stage1_pattern import PatternSelectionResponse
from store_emulator.engine.simulation.engines.pattern_intent_impulse.stage3_impulse import ImpulseResponse
from tests.engine.test_llm_engine_offline import _ScriptedLLM, _context, _intent, _persona


@pytest.mark.parametrize("text", ["enter then browse then buy then pay then exit. " * 1500,
                                "입장 후 둘러보고 구매 후 결제하고 퇴장. " * 1500, "🛒" * 10000])
@pytest.mark.parametrize("ordering", ["planned", "nearest"])
def test_long_pattern_output_cannot_expand_the_next_request_or_drop_a_shopper(collision_store, text, ordering):
    class Model(_ScriptedLLM):
        async def generate_structured_async(self, schema, system, user, **kwargs):
            if issubclass(schema, PatternSelectionResponse):
                return schema.model_validate({"pattern_id": "exploratory", "reasoning": text, "grammar_override": text})
            # The catalog and customer fit; only the prior model's repeated rewrite can overflow this request.
            assert len(system) + len(user) < 6000
            if schema.__name__ == "IntentResponse":
                assert pattern.grammar in user and text not in user
            return await super().generate_structured_async(schema, system, user, **kwargs)

    context = _context(collision_store, _persona())
    pattern = next(p for p in context.behavior_patterns if p.id == "exploratory")
    model = Model(_intent(), ImpulseResponse())
    engine = PatternIntentImpulseEngine(model, AStarPathFinder(), SimulationConfig(route_ordering=ordering))
    decision = asyncio.run(engine.decide_actions(context))
    result = execute_decision(collision_store, "P1", Weekday.MON, "12:00:00", decision, AStarPathFinder(), 1)
    assert result.total_spent == 300 and result.timeline[-1].action == Action.EXIT
    assert decision.trace["stage1"]["grammar_override"] == ""
    assert len(decision.trace["stage1"]["reasoning"]) == 600


@pytest.mark.parametrize("character", ["x", "주", "茶", "🛒"])
@pytest.mark.parametrize("length", [0, 599, 600, 601, 1199, 1200, 1201])
def test_normal_override_is_preserved_and_oversized_rule_is_dropped_whole(character, length):
    text = character * length
    response = PatternSelectionResponse.model_validate({"pattern_id": "custom-pattern", "reasoning": text,
                                                        "grammar_override": text})
    assert response.pattern_id == "custom-pattern"
    assert response.reasoning == text[:600]
    assert response.grammar_override == (text if length <= 1200 else "")


def test_pattern_schema_bounds_optional_prose_without_capping_custom_ids():
    properties = PatternSelectionResponse.model_json_schema()["properties"]
    assert properties["reasoning"]["maxLength"] == 600
    assert properties["grammar_override"]["maxLength"] == 1200
    assert "maxLength" not in properties["pattern_id"]


@pytest.mark.parametrize("mode", ["json", "json_schema"])
def test_http_pattern_repetition_normalizes_before_stage_two_and_cache(monkeypatch, tmp_path, collision_store, mode):
    import json

    import httpx
    from openai import AsyncOpenAI

    from store_emulator.domain.config import LLMConfig
    from store_emulator.engine import llm_client

    calls = []
    original = llm_client.litellm.acompletion

    def respond(request):
        body = json.loads(request.content)
        calls.append(body)
        if len(calls) == 1:
            if mode == "json_schema":
                properties = body["response_format"]["json_schema"]["schema"]["properties"]
                assert properties["grammar_override"]["maxLength"] == 1200
            answer = {"pattern_id": "exploratory", "reasoning": "repeated " * 1000,
                      "grammar_override": "enter browse buy pay exit " * 1000}
        elif len(calls) == 2:
            # Bound the echoed rule text itself: JSON mode also embeds the response schema, whose size is unrelated.
            stage_two = "\n".join(m["content"] for m in body["messages"])
            assert "enter browse buy pay exit" not in stage_two
            assert stage_two.count("repeated ") * len("repeated ") <= 600
            answer = _intent().model_dump(mode="json")
        else:
            assert len(calls) == 3
            answer = {"actions": []}
        return httpx.Response(200, request=request, json={"id": "offline", "object": "chat.completion", "created": 0,
            "model": body["model"], "choices": [{"index": 0, "finish_reason": "stop",
                "message": {"role": "assistant", "content": json.dumps(answer)}}]})

    async def exercise():
        async with httpx.AsyncClient(transport=httpx.MockTransport(respond)) as http:
            transport = AsyncOpenAI(api_key="offline", base_url="http://local.invalid/v1", http_client=http, max_retries=0)

            async def completion(**kwargs):
                return await original(**{**kwargs, "client": transport, "api_key": "offline", "num_retries": 0})

            monkeypatch.setattr(llm_client.litellm, "acompletion", completion)
            client = llm_client.LiteLLMClient(LLMConfig(model="openai/local-pattern", api_base="http://local.invalid/v1",
                structured_output=mode, cache_dir=str(tmp_path)))
            engine = PatternIntentImpulseEngine(client, AStarPathFinder(), SimulationConfig())
            first = await engine.decide_actions(_context(collision_store, _persona()))
            second = await engine.decide_actions(_context(collision_store, _persona()))
            assert first == second and client.get_usage().cached_requests == 3
            assert first.trace["stage1"]["grammar_override"] == ""

    asyncio.run(exercise())
    assert len(calls) == 3
