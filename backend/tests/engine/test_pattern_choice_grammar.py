"""Grammar-capable local models must choose from this visit's actual behavior IDs."""

import asyncio
import json

import httpx
import pytest
from jsonschema import Draft202012Validator
from openai import AsyncOpenAI
from pydantic import ValidationError

from store_emulator.application.presets.behavior import BEHAVIOR_PATTERNS
from store_emulator.domain.config import LLMConfig, SimulationConfig
from store_emulator.domain.types import Action, Weekday
from store_emulator.engine import llm_client
from store_emulator.engine.routing.pathfinder import AStarPathFinder
from store_emulator.engine.simulation.customer_executor import execute_decision
from store_emulator.engine.simulation.engines.pattern_intent_impulse.engine import PatternIntentImpulseEngine
from store_emulator.engine.simulation.engines.pattern_intent_impulse.stage1_pattern import PatternSelectionResponse, pattern_selection_model
from store_emulator.engine.simulation.engines.pattern_intent_impulse.stage3_impulse import ImpulseResponse
from tests.engine.test_llm_engine_offline import _ScriptedLLM, _context, _intent, _persona


@pytest.mark.parametrize("chosen", ["custom-browse-only", '동네/둘러보기"🛒', "x" * 200])
@pytest.mark.parametrize("single", [False, True])
@pytest.mark.parametrize("ordering", ["planned", "nearest"])
def test_actual_http_grammar_prevents_invented_ids_from_selecting_the_first_pattern(monkeypatch, tmp_path, collision_store,
                                                                                 chosen, single, ordering):
    context = _context(collision_store, _persona())
    template = context.behavior_patterns[0]
    target = template.model_copy(update={"id": chosen, "name": "Browse only", "max_products": 0, "allow_no_purchase": True})
    context.behavior_patterns = ([template] if not single else []) + [target]
    expected = [p.id for p in context.behavior_patterns]
    original = llm_client.litellm.acompletion
    calls, schemas = [], []

    def respond(request):
        body = json.loads(request.content)
        calls.append(body)
        if len(calls) == 1:
            schema = body["response_format"]["json_schema"]["schema"]
            schemas.append(schema)
            # Model a provider that obeys its grammar: it can invent an ID only
            # when the transmitted schema permits one.
            wrong = {"pattern_id": "Translated behavior name"}
            answer = wrong if Draft202012Validator(schema).is_valid(wrong) else {"pattern_id": chosen}
        elif len(calls) == 2:
            answer = _intent().model_dump(mode="json")
        else:
            assert len(calls) == 3
            answer = {"actions": []}
        return httpx.Response(200, request=request, json={"id": "offline", "object": "chat.completion", "created": 0,
            "model": body["model"], "choices": [{"index": 0, "finish_reason": "stop",
                "message": {"role": "assistant", "content": json.dumps(answer)}}]})

    async def exercise():
        async with httpx.AsyncClient(transport=httpx.MockTransport(respond)) as http:
            adapter = AsyncOpenAI(api_key="offline", base_url="http://127.0.0.1:8081/v1", http_client=http, max_retries=0)

            async def completion(**kwargs):
                return await original(**{**kwargs, "client": adapter, "api_key": "offline", "num_retries": 0})

            monkeypatch.setattr(llm_client.litellm, "acompletion", completion)
            client = llm_client.LiteLLMClient(LLMConfig(model="openai/pattern-choice", api_base="http://127.0.0.1:8081/v1",
                structured_output="json_schema", cache_dir=str(tmp_path)))
            engine = PatternIntentImpulseEngine(client, AStarPathFinder(), SimulationConfig(route_ordering=ordering))
            decision = await engine.decide_actions(context)
            assert decision.trace["stage1"]["pattern_id"] == chosen
            result = execute_decision(collision_store, "P1", Weekday.MON, "12:00:00", decision, AStarPathFinder(), 1)
            assert not result.purchases and result.total_spent == 0 and decision.trace["dropped_product_limit"] == 1
            assert result.timeline[-1].action == Action.EXIT
            assert await engine.decide_actions(context) == decision and len(calls) == 3

    asyncio.run(exercise())
    schema = schemas[0]
    assert schema["properties"]["pattern_id"]["enum"] == expected
    validator = Draft202012Validator(schema)
    assert not validator.is_valid({}) and not validator.is_valid({"pattern_id": ""})
    assert all(validator.is_valid({"pattern_id": key}) for key in expected)
    assert "enum" not in PatternSelectionResponse.model_json_schema()["properties"]["pattern_id"]


@pytest.mark.parametrize("answer", [{}, {"pattern_id": ""}, {"pattern_id": "unknown-id"}])
def test_non_enforcing_provider_keeps_existing_unknown_or_missing_id_fallback(collision_store, answer):
    class Model(_ScriptedLLM):
        async def generate_structured_async(self, schema, system, user, **kwargs):
            if issubclass(schema, PatternSelectionResponse):
                return schema.model_validate(answer)
            return await super().generate_structured_async(schema, system, user, **kwargs)

    context = _context(collision_store, _persona())
    model = Model(_intent(), ImpulseResponse())
    decision = asyncio.run(PatternIntentImpulseEngine(model, AStarPathFinder(), SimulationConfig()).decide_actions(context))
    assert context.behavior_patterns[0].grammar in model.calls[0][2]
    result = execute_decision(collision_store, "P1", Weekday.MON, "12:00:00", decision, AStarPathFinder(), 1)
    assert result.total_spent == 300


def test_concurrent_visits_keep_custom_pattern_grammars_separate(collision_store):
    class Model(_ScriptedLLM):
        async def generate_structured_async(self, schema, system, user, **kwargs):
            if issubclass(schema, PatternSelectionResponse):
                expected = "pattern-" + kwargs["route"]
                await asyncio.sleep(0)
                assert schema.model_json_schema()["properties"]["pattern_id"]["enum"] == [expected]
                return schema(pattern_id=expected)
            return await super().generate_structured_async(schema, system, user, **kwargs)

    async def exercise():
        model = Model(_intent(), ImpulseResponse())
        engine = PatternIntentImpulseEngine(model, AStarPathFinder(), SimulationConfig())
        contexts = []
        for index in range(6):
            context = _context(collision_store, _persona().model_copy(update={"id": str(index)}))
            context.behavior_patterns = [context.behavior_patterns[0].model_copy(
                update={"id": f"pattern-{index}", "max_products": index % 2})]
            contexts.append(context)
        decisions = await asyncio.gather(*(engine.decide_actions(context) for context in contexts))
        assert [d.trace["stage1"]["pattern_id"] for d in decisions] == [f"pattern-{i}" for i in range(6)]
        assert [sum(a.action == Action.BUY for a in d.actions) for d in decisions] == [0, 1, 0, 1, 0, 1]

    asyncio.run(exercise())


@pytest.mark.parametrize("mode", ["json", "json_schema"])
@pytest.mark.parametrize("ordering", ["planned", "nearest"])
@pytest.mark.parametrize("chosen", [pattern.id for pattern in BEHAVIOR_PATTERNS])
def test_http_pattern_spelling_preserves_grammar_purchase_limit_and_cache(monkeypatch, tmp_path, collision_store,
                                                                        mode, ordering, chosen):
    context = _context(collision_store, _persona())
    pattern = next(pattern for pattern in context.behavior_patterns if pattern.id == chosen)
    before = collision_store.model_dump()
    planned = _intent().model_dump(mode="json")
    planned["actions"].insert(-2, {"nav": "path", "action": "buy", "product_sku": "sku-b",
                                  "quantity": 1, "target": [1, 0], "face": "W"})
    original, calls = llm_client.litellm.acompletion, []

    def respond(request):
        body = json.loads(request.content)
        calls.append(body)
        if len(calls) == 1:
            answer = {"pattern_id": f"\u3000{chosen.upper()}\t", "reasoning": "Keep Chosen Behavior"}
        elif len(calls) == 2:
            answer = planned
        else:
            assert len(calls) == 3
            answer = {"actions": []}
        return httpx.Response(200, request=request, json={"id": "offline", "object": "chat.completion", "created": 0,
            "model": body["model"], "choices": [{"index": 0, "finish_reason": "stop",
                "message": {"role": "assistant", "content": json.dumps(answer)}}]})

    async def exercise():
        async with httpx.AsyncClient(transport=httpx.MockTransport(respond)) as http:
            adapter = AsyncOpenAI(api_key="offline", base_url="http://127.0.0.1:8081/v1", http_client=http, max_retries=0)

            async def completion(**kwargs):
                return await original(**{**kwargs, "client": adapter, "api_key": "offline", "num_retries": 0})

            monkeypatch.setattr(llm_client.litellm, "acompletion", completion)
            client = llm_client.LiteLLMClient(LLMConfig(model="openai/pattern-spelling", api_base="http://127.0.0.1:8081/v1",
                structured_output=mode, cache_dir=str(tmp_path)))
            paths = AStarPathFinder()
            engine = PatternIntentImpulseEngine(client, paths, SimulationConfig(route_ordering=ordering, budget_tolerance=None))
            expected_count = min(2, pattern.max_products)
            expected_spend = 0 if expected_count == 0 else 300 if expected_count == 1 else 500
            for repeat in range(2):
                decision = await engine.decide_actions(context)
                result = execute_decision(collision_store, "P1", Weekday.MON, "12:00:00", decision, paths, 1)
                assert result.total_spent == expected_spend and len(result.purchases) == expected_count
                assert decision.trace["dropped_product_limit"] == 2 - expected_count
                assert decision.trace["stage1"]["pattern_id"] == chosen
                assert decision.trace["stage1"]["reasoning"] == "Keep Chosen Behavior"
                assert result.timeline[-1].action == Action.EXIT
                assert len(calls) == 3 and client.get_usage().cached_requests == 3 * repeat
                assert collision_store.model_dump() == before
            stage2_user = calls[1]["messages"][1]["content"]
            assert pattern.grammar in stage2_user and f"최대 {pattern.max_products}개" in stage2_user

    asyncio.run(exercise())


@pytest.mark.parametrize("chosen,said", [("Custom", " Custom "), ("custom", " custom "), ("Custom", "Custom"),
                                         ("custom", "custom"), ("CUSTOM", "CUSTOM"), ("unknown", "unknown"),
                                         ("", ""), (" Custom ", " Custom ")])
def test_custom_pattern_collisions_exact_ids_and_unknown_fallback_are_preserved(chosen, said):
    ids = ["Custom", "custom"] + ([" Custom "] if chosen == " Custom " else [])
    patterns = [BEHAVIOR_PATTERNS[0].model_copy(update={"id": key}) for key in ids]
    schema = pattern_selection_model(patterns)
    assert schema(pattern_id=said).pattern_id == chosen


@pytest.mark.parametrize("value", [None, 1, True, [], {}])
def test_wrong_pattern_id_types_still_fail(value):
    with pytest.raises(ValidationError):
        pattern_selection_model(BEHAVIOR_PATTERNS).model_validate_json(json.dumps({"pattern_id": value}), strict=True)
