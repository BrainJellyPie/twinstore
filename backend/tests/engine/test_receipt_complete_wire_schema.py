"""Native receipt output must explicitly address every field, including purchased lines."""

from copy import deepcopy

import pytest
from jsonschema import Draft202012Validator, ValidationError

from store_emulator.engine.vision_inputs import _ReceiptVLM


READING = {"store": "Corner Store", "date": "2026-10-27", "time": "14:05", "currency": "USD",
    "lines": [{"name": "Tea", "quantity": 2, "unit_price": 2.5, "line_total": 5}], "total": 5}


@pytest.mark.parametrize("field", ["store", "date", "time", "currency", "lines", "total"])
def test_wire_requires_a_value_for_every_receipt_field(field):
    payload = deepcopy(READING)
    del payload[field]
    with pytest.raises(ValidationError):
        Draft202012Validator(_ReceiptVLM.model_json_schema()).validate(payload)


@pytest.mark.parametrize("field", ["name", "quantity", "unit_price", "line_total"])
def test_wire_cannot_silently_default_a_purchased_quantity_or_amount(field):
    payload = deepcopy(READING)
    del payload["lines"][0][field]
    with pytest.raises(ValidationError):
        Draft202012Validator(_ReceiptVLM.model_json_schema()).validate(payload)


@pytest.mark.parametrize("lines", [[], [{"name": "", "quantity": 1, "unit_price": None, "line_total": None}],
    [{"name": "Tea", "quantity": 0.5, "unit_price": 4, "line_total": 2}],
    [{"name": "Tea", "quantity": 1, "unit_price": 0, "line_total": 0}]])
def test_complete_wire_can_express_unknown_free_and_fractional_purchases(lines):
    payload = {"store": "", "date": "", "time": "", "currency": "", "lines": lines, "total": None}
    Draft202012Validator(_ReceiptVLM.model_json_schema()).validate(payload)
    assert _ReceiptVLM.model_validate(payload).model_dump() == payload


def test_existing_partial_receipt_data_remains_readable_without_inventing_lines():
    assert _ReceiptVLM.model_validate({"store": None, "total": 6.6}).model_dump() == {
        "store": "", "date": "", "time": "", "currency": "", "lines": [], "total": 6.6}
    reading = _ReceiptVLM.model_validate({"lines": [{"name": "Tea", "line_total": 2}]})
    assert reading.lines[0].model_dump() == {"name": "Tea", "quantity": 1, "unit_price": None, "line_total": 2}
