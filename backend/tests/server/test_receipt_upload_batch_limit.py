"""Every accepted receipt photo batch must fit the correction-review API."""
from unittest.mock import Mock

import pytest
from fastapi.testclient import TestClient

from store_emulator.application import vision_inputs
from store_emulator.application.vision_inputs import ReceiptsResult


@pytest.mark.parametrize("count,expected", [(100, 200), (101, 422)])
def test_receipt_upload_respects_review_batch_limit(tmp_path, monkeypatch, count, expected):
    monkeypatch.chdir(tmp_path)
    reader = Mock(return_value=ReceiptsResult(receipts=[], matched_lines=0, unmatched_lines=0, csv="", currency="USD"))
    monkeypatch.setattr(vision_inputs, "read_receipts", reader)
    from store_emulator.server.main import app
    response = TestClient(app, raise_server_exceptions=False).post("/api/projects/proj_test/receipts", files=[("photos", (f"receipt-{i}.png", b"photo", "image/png")) for i in range(count)])
    assert response.status_code == expected, response.text
    if expected == 200:
        reader.assert_called_once()
        assert len(reader.call_args.args[1]) == count
    else:
        reader.assert_not_called()
