"""Repeated receipt timestamps must not incur full date parsing for every product line."""

from collections import Counter

import pytest

from store_emulator.application import pos
from tests.engine.test_fidelity_receipt_scope import export


@pytest.mark.parametrize("suffix", ["csv", "xlsx"])
def test_repeated_timestamps_share_parse_work_without_changing_local_times(monkeypatch, suffix):
    clocks = [("2026-10-19 09:00:00+09:00", 9), ("2026-10-19 09:00:00-04:00", 9),
              ("2026-10-19", None), ("2026-99-99 25:99:00", None), ("10 PM", 22)]
    rows = [{"receipt_id": f"r{i}", "sku": "chips", "timestamp": clocks[i % len(clocks)][0], "date": "2026-10-19"}
            for i in range(2000)]
    data = export(rows, suffix)
    original = pos.parse_date
    calls = Counter()

    def observed(value, *args, **kwargs):
        calls[str(value)] += 1
        return original(value, *args, **kwargs)

    monkeypatch.setattr(pos, "parse_date", observed)
    lines = pos.parse_pos_csv(data, f"pos.{suffix}")
    assert len(lines) == 2000
    assert [line.hour for line in lines] == [clocks[i % len(clocks)][1] for i in range(2000)]
    assert all(line.transaction_scope == (("date", "2026-10-19"),) for line in lines)
    # A small fixed set of clocks should need a small fixed amount of date-parser work, including invalid values.
    assert sum(calls.values()) <= 2 * len(clocks), calls
