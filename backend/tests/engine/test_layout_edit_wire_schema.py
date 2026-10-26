"""The local grammar separates operation targets and requires their values."""

import pytest
from jsonschema import Draft202012Validator

from store_emulator.engine.layout_edit import _EditDraft


@pytest.mark.parametrize("change", [
    {"kind": "price", "product": "Tea", "price": 3},
    {"kind": "discount", "product": "Tea", "percent": -10, "discount_basis": "regular"},
    {"kind": "discount", "product": "Tea", "percent": -100, "discount_basis": "current"},
    {"kind": "promo", "product": "Chips", "promo": "SALE"},
    {"kind": "move", "product": "Tea", "shelf": "Drinks", "level": 3},
    {"kind": "move", "product": "Tea", "shelf": "Drinks"},
    {"kind": "category_price", "category": "Drinks", "percent": -10},
    {"kind": "category_price", "category": "Drinks", "percent": 10},
])
def test_minimal_operations_and_canonical_cache_entries_remain_readable(change):
    payload = {"name": "Edit", "changes": [change]}
    Draft202012Validator(_EditDraft.model_json_schema()).validate(payload)
    cached = _EditDraft.model_validate(payload).model_dump()
    assert _EditDraft.model_validate(cached).model_dump() == cached


@pytest.mark.parametrize("percent", [-10, -100])
def test_legacy_discount_replies_and_cache_entries_default_to_regular_price(percent):
    payload = {"name": "Edit", "changes": [{"kind": "discount", "product": "Tea", "percent": percent}]}
    draft = _EditDraft.model_validate(payload)
    assert draft.changes[0].discount_basis == "regular"
    assert _EditDraft.model_validate(draft.model_dump()) == draft


@pytest.mark.parametrize("change", [
    {"kind": "move", "product": "Tea", "level": 3, "category": "Drinks"},  # actual CPU reply
    {"kind": "move", "product": "Tea", "shelf": "Drinks", "level": None},
    {"kind": "move", "product": "Tea", "shelf": "Drinks", "level": 0},
    {"kind": "move", "product": "Tea", "shelf": "Drinks", "level": 5},
    {"kind": "move", "product": "Tea", "shelf": ""},
    {"kind": "price", "product": "Tea"},
    {"kind": "price", "product": "Tea", "price": None},
    {"kind": "price", "product": "Tea", "price": 3, "percent": -10},
    {"kind": "discount", "product": "Tea", "price": 4.5},
    {"kind": "discount", "product": "Tea", "percent": -10},
    {"kind": "discount", "product": "Tea", "percent": -10, "discount_basis": "unknown"},
    {"kind": "discount", "product": "Tea", "percent": 10, "discount_basis": "regular"},
    {"kind": "discount", "product": "Tea", "percent": 0, "discount_basis": "regular"},
    {"kind": "discount", "product": "Tea", "percent": -100.01, "discount_basis": "current"},
    {"kind": "promo", "product": "Chips"},
    {"kind": "promo", "product": "Chips", "promo": ""},
    {"kind": "category_price", "shelf": "Drinks", "percent": -10},
    {"kind": "category_price", "category": "Drinks", "percent": None},
    {"kind": "category_price", "category": "Drinks", "percent": 301},
    {"kind": "price", "product": "", "price": 3},
])
def test_wrong_fields_missing_values_and_out_of_range_values_fail_the_wire_grammar(change):
    assert not Draft202012Validator(_EditDraft.model_json_schema()).is_valid({"name": "Edit", "changes": [change]})
