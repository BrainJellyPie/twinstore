"""Expose only additional reactions that fit the already validated planned basket."""
import asyncio

import pytest
from jsonschema import Draft202012Validator
from litellm.exceptions import BadRequestError

from store_emulator.domain.config import SimulationConfig
from store_emulator.domain.rack import SlotItem
from store_emulator.domain.types import Action, Weekday
from store_emulator.engine.routing.pathfinder import AStarPathFinder
from store_emulator.engine.simulation.customer_executor import execute_decision
from store_emulator.engine.simulation.engines.pattern_intent_impulse import stage2_intent, stage3_impulse
from store_emulator.engine.simulation.engines.pattern_intent_impulse.engine import PatternIntentImpulseEngine
from tests.engine.test_llm_engine_offline import _ScriptedLLM, _context, _persona
from tests.engine.test_llm_impulse_exposure import buy, fixture


@pytest.mark.parametrize("maximum", [0, 1, 2])
@pytest.mark.parametrize("planned_count", [0, 1, 2])
@pytest.mark.parametrize("price", [0, 100])
@pytest.mark.parametrize("recovery", [False, True])
def test_full_and_recovered_impulse_schemas_respect_remaining_capacity(maximum, planned_count, price, recovery):
    store, intent = fixture()
    items = [SlotItem(sku=f"seen{i}", name=f"Tea {i}", price=price) for i in range(6)]
    slot = store.racks[0].slots[0]
    slot.items = items[:3]
    store.racks[0].slots.append(slot.model_copy(update={"level": 4, "items": items[3:]}))
    for i in range(planned_count):
        intent.actions.insert(-1, buy(f"seen{i}", (2, 2)).model_copy(update={"quantity": 2}))
    records = stage2_intent.catalog_records(store)
    code = next(iter(records))
    schemas, prompts = [], []

    class Client(_ScriptedLLM):
        async def generate_structured_async(self, response_model, system_prompt, user_prompt, **kwargs):
            if issubclass(response_model, stage3_impulse.ImpulseResponse):
                schemas.append(response_model.model_json_schema())
                prompts.append(system_prompt)
                if recovery and len(schemas) == 1:
                    raise BadRequestError("request (8500 tokens) exceeds the available context size (8192 tokens)",
                                          model="local", llm_provider="openai")
            elif issubclass(response_model, stage2_intent.CatalogSelection):
                return response_model.model_validate({"codes": [code]})
            return await super().generate_structured_async(response_model, system_prompt, user_prompt, **kwargs)

    client = Client(intent, stage3_impulse.ImpulseResponse(actions=[
        {"action": "browse", "nav": "path", "target": (2, 2), "face": "S"}]))
    context = _context(store, _persona(10000))
    pattern = next(p for p in context.behavior_patterns if p.id == "exploratory")
    context.behavior_patterns = [pattern.model_copy(update={"max_products": maximum})]
    pathfinder = AStarPathFinder()
    engine = PatternIntentImpulseEngine(client, pathfinder, SimulationConfig(budget_tolerance=None))
    decision = asyncio.run(engine.decide_actions(context))
    assert len(schemas) == 1 + recovery
    for schema, prompt in zip(schemas, prompts):
        validator = Draft202012Validator(schema)
        assert validator.is_valid({"actions": []})
        assert validator.is_valid({"actions": [{"action": "browse", "target": [2, 2]}]})
        assert validator.is_valid({"actions": [{"action": "buy", "product_sku": code, "quantity": 1}]}) == (planned_count < maximum)
        assert not validator.is_valid({"actions": [{"action": "pay"}]})
        assert not validator.is_valid({"actions": [{"action": "exit"}]})
        if planned_count >= maximum:
            assert "No additional purchases are allowed" in prompt
    receipt = execute_decision(store, "P1", Weekday.MON, "12:00:00", decision, pathfinder, 1)
    assert [(p.product_sku, p.quantity) for p in receipt.purchases] == [(f"seen{i}", 2) for i in range(min(planned_count, maximum))]
    assert receipt.total_spent == price * 2 * min(planned_count, maximum)
    assert receipt.timeline[-1].action == Action.EXIT
    assert any(a["action"] == "browse" for a in decision.trace["stage3"]["actions"])
