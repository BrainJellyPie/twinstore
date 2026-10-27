"""Model action schemas describe usable operations while canonical caches stay readable."""
import json

import pytest
from jsonschema import Draft202012Validator

from store_emulator.domain.rack import SlotItem
from store_emulator.engine.simulation.engines.pattern_intent_impulse import stage2_intent as stage
from store_emulator.engine.simulation.engines.pattern_intent_impulse.stage3_impulse import ImpulseResponse


RECORDS = {"@P1": SlotItem(sku="tea", name="Tea", price=250)}


@pytest.mark.parametrize("base", [stage.IntentResponse, ImpulseResponse])
@pytest.mark.parametrize("action", [
    {"action": "enter"}, {"action": "exit"}, {"action": "pay"},
    {"action": "move", "target": [1, 2]},
    {"action": "browse", "target": [1, 2], "face": "N", "dwell": 120},
    {"action": "buy", "product_sku": "@P1", "quantity": 2},
    {"action": "wander", "nav": "area", "area": [0, 0, 3, 3]},
    {"action": "wander", "nav": "path", "target": [1, 2]},
])
def test_operation_shapes_validate_and_canonical_round_trips_preserve_fields(base, action):
    schema = stage.catalog_response_model(base, RECORDS, max_quantity=2)
    value = {"actions": [action]}
    assert Draft202012Validator(schema.model_json_schema()).is_valid(value) == (action["action"] in base.action_kinds)
    result = schema.model_validate_json(json.dumps(value), strict=True)
    assert result.actions[0].action == action["action"]
    assert schema.model_validate_json(result.model_dump_json(), strict=True) == result


@pytest.mark.parametrize("action", [
    {"nav": "area", "area": [0, 0, 3, 3], "quantity": 1},
    {"action": None, "nav": "path"}, {"action": "unknown"},
    {"action": "move"}, {"action": "browse", "target": None},
    {"action": "move", "target": [1]}, {"action": "browse", "target": [True, 2]},
    {"action": "enter", "quantity": 1}, {"action": "exit", "nav": "area"},
    {"action": "buy", "product_sku": "@P1"},
    {"action": "buy", "product_sku": "", "quantity": 1},
    {"action": "buy", "product_sku": "@P2", "quantity": 1},
    {"action": "buy", "product_sku": "tea", "quantity": 1},
    {"action": "buy", "product_sku": "@P1", "quantity": 0},
    {"action": "buy", "product_sku": "@P1", "quantity": 3},
    {"action": "buy", "product_sku": "@P1", "quantity": 1, "area": [0, 0, 3, 3]},
    {"action": "wander", "area": [0, 0, 3, 3]},
    {"action": "wander", "nav": "area", "target": [1, 2]},
    {"action": "wander", "nav": "path", "target": [1, 2], "area": [0, 0, 3, 3]},
    {"action": "browse", "target": [1, 2], "dwell": 121},
    {"action": "buy", "product_sku": "@P1", "quantity": 1, "product_level": 4},
])
def test_wire_rejects_anonymous_incomplete_and_unrelated_fields(action):
    schema = stage.catalog_response_model(stage.IntentResponse, RECORDS, max_quantity=2)
    assert not Draft202012Validator(schema.model_json_schema()).is_valid({"actions": [action]})


@pytest.mark.parametrize("base", [stage.IntentResponse, ImpulseResponse])
def test_empty_catalog_cannot_emit_a_native_purchase_but_can_leave(base):
    schema = stage.catalog_response_model(base, {}, max_quantity=1)
    validator = Draft202012Validator(schema.model_json_schema())
    assert validator.is_valid({"actions": [{"action": "exit"}]}) == ("exit" in base.action_kinds)
    assert validator.is_valid({"actions": []})
    assert not validator.is_valid({"actions": [{"action": "buy", "product_sku": "@P1", "quantity": 1}]})
    assert schema.model_validate_json('{"actions":[{"nav":"leave"}]}', strict=True).actions[0].nav == "leave"


def test_canonical_legacy_actions_and_non_enforcing_quantities_stay_readable():
    schema = stage.catalog_response_model(stage.IntentResponse, RECORDS, max_quantity=2)
    legacy = {"actions": [{"nav": "path", "action": "buy", "product_sku": "tea", "quantity": 10**20,
                           "area": None, "target": [1, 2], "description": "", "face": None}]}
    result = schema.model_validate_json(json.dumps(legacy), strict=True)
    assert result.actions[0].quantity == 10**20  # The executor retains responsibility for its existing clamp.
    assert result.actions[0].product_sku == "tea"
    assert schema.model_validate_json(result.model_dump_json(), strict=True) == result
