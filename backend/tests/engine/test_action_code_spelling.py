"""Offer aliases may be recovered without turning real SKU identifiers into another purchase."""

import pytest

from store_emulator.domain.rack import SlotItem
from store_emulator.engine.simulation.engines.pattern_intent_impulse import stage2_intent
from store_emulator.engine.simulation.engines.pattern_intent_impulse.stage3_impulse import ImpulseResponse
from tests.engine.test_llm_catalog_offers import offers


@pytest.mark.parametrize("sku", ["@P1", "@p1", " @P1 ", "\u3000@p1\t", "@@p1"])
@pytest.mark.parametrize("base", [stage2_intent.IntentResponse, ImpulseResponse])
@pytest.mark.parametrize("focused", [False, True])
def test_aliases_avoid_case_and_space_collisions_with_every_real_sku(sku, base, focused):
    store = offers("level")
    real = SlotItem(sku=sku, name="Literal SKU product", price=900)
    store.racks[0].slots[0].items.append(real)
    before = store.model_dump()
    records = stage2_intent.catalog_records(store)
    code = next(key for key, item in records.items() if item.price == 700)
    raw_skus = {item.sku for rack in store.racks for slot in rack.slots for item in slot.items}
    assert not {key.casefold() for key in records} & {value.strip().casefold() for value in raw_skus}
    if focused:
        records = {code: records[code]}  # The colliding real SKU remains in the store, outside the model shortlist.
    schema = stage2_intent.catalog_response_model(base, records)
    response = schema.model_validate({"actions": [
        {"action": "buy", "nav": "path", "product_sku": sku, "target": [3, 1], "face": "N"},
        {"action": "buy", "nav": "path", "product_sku": f"\u3000{code.lower()}\t", "target": [3, 1], "face": "N"},
    ]})
    decoded = stage2_intent.decode_catalog_response(base, response, records, store)
    assert [action.product_sku for action in decoded.actions] == [sku, "tea"]
    assert decoded.actions[1].product_level == 4 and decoded.actions[1].product_block == 0
    assert response.actions[1].product_sku == f"\u3000{code.lower()}\t" and store.model_dump() == before


@pytest.mark.parametrize("said", ["TEA", " tea ", "@P999", "P1", "@P1-extra", "@ P1", ""])
def test_recovery_does_not_rewrite_raw_skus_or_invent_unlisted_codes(said):
    store = offers("level")
    records = stage2_intent.catalog_records(store)
    schema = stage2_intent.catalog_response_model(stage2_intent.IntentResponse, records)
    response = schema.model_validate({"actions": [{"action": "buy", "nav": "path", "product_sku": said}]})
    decoded = stage2_intent.decode_catalog_response(stage2_intent.IntentResponse, response, records, store)
    assert decoded.actions[0].product_sku == said


def test_case_distinct_aliases_remain_ambiguous_without_an_exact_match():
    store = offers("level")
    records = {"@Pa1": store.racks[0].slots[0].items[0], "@pA1": store.racks[0].slots[1].items[0]}
    schema = stage2_intent.catalog_response_model(stage2_intent.IntentResponse, records)
    response = schema.model_validate({"actions": [{"action": "buy", "nav": "path", "product_sku": "@pa1"}]})
    decoded = stage2_intent.decode_catalog_response(stage2_intent.IntentResponse, response, records, store)
    assert decoded.actions[0].product_sku == "@pa1" and decoded.actions[0].product_level is None
