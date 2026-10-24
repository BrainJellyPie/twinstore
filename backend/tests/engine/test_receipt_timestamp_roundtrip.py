"""Reviewed timestamps must retain the same local date and hour in POS evidence."""

from datetime import datetime

import pytest

from store_emulator.application.pos import parse_pos_csv
from store_emulator.domain.vision_inputs import ReceiptLine, ReceiptReading
from store_emulator.engine.receipt_review import review_receipts


def reading(timestamp: str) -> ReceiptReading:
    return ReceiptReading(
        receipt_id="receipt-1", currency="USD", timestamp=timestamp,
        lines=[ReceiptLine(name="Tea", sku="tea", quantity=1, unit_price=100)],
    )


@pytest.mark.parametrize("timestamp", [
    "2026-10-21 14:05", "2026-10-21T14:05:59.123456", "20261021T140500",
    "2026-W43-3T14:05", "2026W433T1405", "2026-W43T14:05", "2026W43T14",
    "2026W433T14", "20261021T14", "2026-10-21X14:05", "2026-10-21\u202814:05",
    "2026-10-21T00:00", "2024-02-29T23:59:59.999999", "2020-W53-7T23:59",
    "2021-W01-1T00:00", "2000-02-29T12:00", "2026-10-21T14:05:59,123456",
])
def test_reviewed_timestamp_survives_csv_and_pos(timestamp: str) -> None:
    original = reading(timestamp)
    expected = datetime.fromisoformat(timestamp)
    result = review_receipts([original], {"tea": "Tea"}, "USD")

    assert result.ready, result.issues
    assert original.timestamp == timestamp
    pos = parse_pos_csv(result.csv.encode())[0]
    assert pos.hour == expected.hour
    assert ("date", expected.date().isoformat()) in pos.transaction_scope
    assert pos.quantity == 1 and pos.unit_price == 100
    assert result.receipts[0].timestamp == expected.isoformat(sep=" ")


@pytest.mark.parametrize("timestamp", [
    "2026-10-21", "20261021", "2026-W43-3", "2026W433", "2026-W43", "2026W43",
])
def test_date_only_still_requires_explicit_time(timestamp: str) -> None:
    result = review_receipts([reading(timestamp)], {"tea": "Tea"}, "USD")
    assert not result.ready and not result.csv
    assert "time_missing" in {issue.code for issue in result.issues}


@pytest.mark.parametrize("timestamp", [
    "2026-10-21T14:05Z", "20261021T1405+0900", "2026-W43-3T14:05-04:00",
])
def test_timezone_is_not_silently_converted_or_removed(timestamp: str) -> None:
    result = review_receipts([reading(timestamp)], {"tea": "Tea"}, "USD")
    assert not result.ready and not result.csv
    assert "timezone" in {issue.code for issue in result.issues}


@pytest.mark.parametrize("timestamp", [
    "2026-02-29T14:05", "2026-10-21T24:00", "2026-W54-1T14:05", "14:05", " ",
])
def test_invalid_timestamps_remain_errors(timestamp: str) -> None:
    result = review_receipts([reading(timestamp)], {"tea": "Tea"}, "USD")
    assert not result.ready and not result.csv
    assert "timestamp" in {issue.code for issue in result.issues}


def test_absent_timestamp_remains_optional_with_a_warning() -> None:
    result = review_receipts([reading("")], {"tea": "Tea"}, "USD")
    assert result.ready
    assert [(issue.code, issue.severity) for issue in result.issues] == [("time_missing", "warning")]
    pos = parse_pos_csv(result.csv.encode())[0]
    assert pos.hour is None and pos.transaction_scope == ()
