import pytest

from store_emulator.application.pos import parse_pos_csv
from store_emulator.domain.vision_inputs import ReceiptLine, ReceiptReading
from store_emulator.engine.receipt_review import review_receipts


def receipt(**line_changes: object) -> ReceiptReading:
    line = ReceiptLine.model_validate({"name": "Cola", "sku": "A1", "quantity": 2, "unit_price": 249,
                                      "line_total": 450, **line_changes})
    return ReceiptReading(receipt_id="r1", currency="USD", timestamp="2026-10-21 14:05", lines=[line])


def test_discount_and_total_only_lines_keep_paid_value() -> None:
    for price in [249, None]:
        result = review_receipts([receipt(unit_price=price)], {"A1": "Cola"}, "USD")
        assert result.ready and result.receipts[0].lines[0].matched
        pos = parse_pos_csv(result.csv.encode())
        assert pos[0].quantity * pos[0].unit_price == 450
        assert pos[0].hour == 14
    assert "line_total" in {i.code for i in review_receipts([receipt()], {"A1": "Cola"}, "USD").issues}


@pytest.mark.parametrize("change,code", [
    ({"sku": "unknown", "matched": True}, "sku"),
    ({"quantity": 0}, "quantity"), ({"quantity": -1}, "quantity"),
    ({"quantity": 1e-320}, "amount"),
    ({"unit_price": -1}, "price"), ({"line_total": -1}, "price"),
    ({"unit_price": None, "line_total": None}, "price_missing"),
])
def test_bad_sales_evidence_has_no_csv(change: dict[str, object], code: str) -> None:
    result = review_receipts([receipt(**change)], {"A1": "Cola"}, "USD")
    assert not result.ready and result.csv == ""
    assert code in {i.code for i in result.issues if i.severity == "error"}


def test_free_and_weighted_items_are_valid_and_input_is_unchanged() -> None:
    reading = receipt(quantity=0.25, unit_price=None, line_total=0)
    result = review_receipts([reading], {"A1": "Cola"}, "USD")
    assert result.ready and not reading.lines[0].matched
    assert parse_pos_csv(result.csv.encode())[0].unit_price == 0


def test_duplicate_ids_currency_empty_and_bad_time_are_blocked() -> None:
    reading = receipt()
    reading.currency = "KRW"
    reading.timestamp = "2026-10-21"
    result = review_receipts([reading, reading], {"A1": "Cola"}, "USD")
    assert not result.ready
    assert {"receipt_id", "currency", "time_missing"} <= {i.code for i in result.issues}
    assert not review_receipts([], {}, "USD").ready
    assert not review_receipts([ReceiptReading(receipt_id="empty", currency="USD")], {}, "USD").ready


def test_csv_quotes_ids_and_skus_and_warns_about_tax() -> None:
    reading = receipt(sku='sku,"A"')
    reading.receipt_id = 'receipt,"1"'
    reading.timestamp = ""
    reading.total = 500
    result = review_receipts([reading], {'sku,"A"': "Cola"}, "USD")
    assert result.ready
    assert {"time_missing", "subtotal"} <= {i.code for i in result.issues}
    pos = parse_pos_csv(result.csv.encode())
    assert pos[0].transaction_id == reading.receipt_id and pos[0].sku == 'sku,"A"'
