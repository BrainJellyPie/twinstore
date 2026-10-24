"""Model answers cannot select offers through engine-only placement hints."""

import asyncio

import pytest

from store_emulator.domain.action import CustomerAction
from store_emulator.domain.config import SimulationConfig
from store_emulator.domain.rack import Slot, SlotItem
from store_emulator.domain.types import Action, Face, Weekday
from store_emulator.engine.routing.pathfinder import AStarPathFinder
from store_emulator.engine.simulation.customer_executor import execute_decision
from store_emulator.engine.simulation.engines.pattern_intent_impulse.engine import PatternIntentImpulseEngine
from store_emulator.engine.simulation.engines.pattern_intent_impulse.stage2_intent import IntentResponse
from store_emulator.engine.simulation.engines.pattern_intent_impulse.stage3_impulse import ImpulseResponse
from tests.engine.test_llm_engine_offline import _ScriptedLLM, _context, _intent, _persona


@pytest.mark.parametrize("stage", ["intent", "impulse"])
@pytest.mark.parametrize("ordering", ["planned", "nearest"])
@pytest.mark.parametrize("hints", [
    {"product_level": 4}, {"product_block": 1}, {"product_block": 1, "product_level": 4},
    {"product_level": "eye level"}, {"product_block": {"rack": "another"}},
    {"origin": ["model-chosen"]}, {"product_level": None, "product_block": None, "origin": None},
    {},
])
def test_hidden_fields_cannot_change_purchase_value_or_fail_a_valid_response(collision_store, stage, ordering, hints):
    rack = collision_store.racks[0]
    rack.shape = [[1], [1]]
    rack.slots.extend([
        Slot(block=0, face=Face.E, level=4, items=[SlotItem(sku="sku-a", name="Other level", price=900)]),
        Slot(block=1, face=Face.E, level=1, items=[SlotItem(sku="sku-a", name="Other block", price=500)]),
        Slot(block=1, face=Face.E, level=4, items=[SlotItem(sku="sku-a", name="Other offer", price=700)]),
    ])
    raw = _intent().model_dump()
    action = raw["actions"][2]
    action.update(hints)
    if stage == "intent":
        intent = IntentResponse.model_validate(raw)
        impulse = ImpulseResponse()
    else:
        raw["actions"] = [a for a in raw["actions"] if a["action"] != Action.BUY]
        intent = IntentResponse.model_validate(raw)
        impulse = ImpulseResponse.model_validate({"actions": [action]})
    supplied = intent if stage == "intent" else impulse
    chosen = next(a for a in supplied.actions if a.action == Action.BUY)
    assert chosen.product_block is None and chosen.product_level is None
    assert chosen.origin == "planned"
    llm = _ScriptedLLM(intent, impulse)
    engine = PatternIntentImpulseEngine(llm, AStarPathFinder(),
                                        SimulationConfig(route_ordering=ordering, budget_tolerance=None))
    decision = asyncio.run(engine.decide_actions(_context(collision_store, _persona())))
    result = execute_decision(collision_store, "P1", Weekday.MON, "12:00:00", decision, AStarPathFinder(), 1)
    # Visibility presents the level-4 offer to the impulse model; even a
    # canonical SKU response must buy that offer, independent of injected hints.
    if stage == "impulse":
        assert "Other level 900¢" in llm.calls[-1][2]
    assert result.total_spent == (2700 if stage == "impulse" else 300) and len(result.purchases) == 1
    assert (result.purchases[0].product_block, result.purchases[0].product_level) == (0, 4 if stage == "impulse" else 1)
    assert result.purchases[0].origin == ("planned" if stage == "intent" else "impulse")
    assert result.purchases[0].quantity == 3
    assert action == {**_intent().model_dump()["actions"][2], **hints}  # Do not mutate the caller's data.


@pytest.mark.parametrize("schema", [IntentResponse, ImpulseResponse])
def test_engine_actions_passed_as_models_are_copied_without_changing_the_source(schema):
    action = CustomerAction(nav="path", action=Action.BUY, product_sku="tea", product_block=2, product_level=4,
                            origin="impulse", quantity=2)
    response = schema(actions=[action])
    assert response.actions[0].product_block is None and response.actions[0].product_level is None
    assert response.actions[0].origin == "planned" and response.actions[0].quantity == 2
    assert action.product_block == 2 and action.product_level == 4 and action.origin == "impulse"


@pytest.mark.parametrize("schema", [IntentResponse, ImpulseResponse])
def test_actual_model_errors_are_still_validated_and_internal_fields_stay_hidden(schema):
    from pydantic import ValidationError

    with pytest.raises(ValidationError):
        schema.model_validate({"actions": [{"nav": "path", "action": "invented", "product_level": "ignored"}]})
    data = schema.model_json_schema()
    action_type = data["properties"]["actions"]["items"]["$ref"].rsplit("/", 1)[-1]
    properties = data["$defs"][action_type]["properties"]
    assert not {"origin", "product_block", "product_level"} & properties.keys()


@pytest.mark.parametrize("schema", [IntentResponse, ImpulseResponse])
@pytest.mark.parametrize("mode", ["json", "json_schema"])
@pytest.mark.parametrize("hints", [{"product_block": 1, "product_level": 4, "origin": "other"},
                                   {"product_block": [], "product_level": "eye", "origin": {"source": "model"}}])
def test_http_and_existing_cache_apply_the_same_model_boundary(monkeypatch, tmp_path, schema, mode, hints):
    import json

    import httpx
    from openai import AsyncOpenAI

    from store_emulator.domain.config import LLMConfig
    from store_emulator.engine import llm_client

    calls = []
    original = llm_client.litellm.acompletion

    def respond(request):
        calls.append(json.loads(request.content))
        raw = {"actions": [{"nav": "path", "action": "buy", "product_sku": "tea", "target": [1, 2], "face": "S", **hints},
                           {"nav": "area", "action": "wander", "area": [0, 1, 2, 3], "target": [0, 1]}]}
        return httpx.Response(200, request=request, json={"id": "offline", "object": "chat.completion", "created": 0,
            "model": "local", "choices": [{"index": 0, "finish_reason": "stop",
                "message": {"role": "assistant", "content": json.dumps(raw)}}]})

    async def exercise():
        async with httpx.AsyncClient(transport=httpx.MockTransport(respond)) as http:
            transport = AsyncOpenAI(api_key="offline", base_url="http://local.invalid/v1", http_client=http, max_retries=0)

            async def completion(**kwargs):
                return await original(**{**kwargs, "client": transport, "api_key": "offline", "num_retries": 0})

            monkeypatch.setattr(llm_client.litellm, "acompletion", completion)
            client = llm_client.LiteLLMClient(LLMConfig(model="openai/local-action-fields", api_base="http://local.invalid/v1",
                structured_output=mode, cache_dir=str(tmp_path)))
            first = await client.generate_structured_async(schema, "Plan a visit", "Tea", max_retries=1)
            path, = tmp_path.glob("*/*.json")
            saved = json.loads(path.read_text())
            assert saved["result"]["actions"][0]["product_level"] is None
            # Older cache entries may still contain model-supplied internal hints.
            saved["result"]["actions"][0].update(hints)
            path.write_text(json.dumps(saved))
            second = await client.generate_structured_async(schema, "Plan a visit", "Tea", max_retries=1)
            assert first.model_dump() == second.model_dump() and client.get_usage().cached_requests == 1
            assert first.actions[0].product_sku == "tea" and first.actions[0].origin == "planned"
            assert first.actions[0].product_block is None and first.actions[0].product_level is None
            assert first.actions[0].target == (1, 2) and first.actions[0].face == Face.S
            assert first.actions[1].area == (0, 1, 2, 3) and first.actions[1].target == (0, 1)

    asyncio.run(exercise())
    assert len(calls) == 1


@pytest.mark.parametrize("schema", [IntentResponse, ImpulseResponse])
@pytest.mark.parametrize("field,good,bad", [
    ("target", [1, 2], [1]), ("target", [1, 2], [1, 2, 3]),
    ("target", [1, 2], [True, 2]), ("target", [1, 2], ["1", 2]),
    ("area", [0, 1, 2, 3], [0, 1, 2]), ("area", [0, 1, 2, 3], [0, 1, 2, 3, 4]),
    ("area", [0, 1, 2, 3], [0, 1, 2, 3.5]), ("area", [0, 1, 2, 3], [0, 1, None, 3]),
])
def test_json_coordinates_preserve_strict_length_and_element_validation(schema, field, good, bad):
    import json
    from pydantic import ValidationError

    data = {"actions": [{"nav": "path", field: good, "product_level": {"ignored": True}}]}
    response = schema.model_validate_json(json.dumps(data), strict=True)
    assert getattr(response.actions[0], field) == tuple(good)
    data["actions"][0][field] = bad
    with pytest.raises(ValidationError):
        schema.model_validate_json(json.dumps(data), strict=True)
