"""Reject ambiguous POS uploads before touching an existing fidelity report."""

from unittest.mock import Mock

from fastapi.testclient import TestClient
import pytest

from store_emulator.application import simulation
from store_emulator.server.main import app
from tests.engine.test_pos_duplicate_columns import data


@pytest.mark.parametrize("extension", ["csv", "xlsx"])
@pytest.mark.parametrize("headers,values", [
    (["receipt_id", "sku", "SKU"], ["r", "tea", "coffee"]),
    (["receipt_id", "sku", "store_id", "Store ID"], ["r", "tea", "shop-a", "shop-b"]),
])
def test_ambiguous_headers_return_400_and_preserve_saved_evidence(tmp_path, monkeypatch, extension, headers, values):
    monkeypatch.chdir(tmp_path)
    base = tmp_path / "run"
    output = base / "output"
    output.mkdir(parents=True)
    saved = output / "fidelity.json"
    before = b'{"previous_evidence": true}\n'
    saved.write_bytes(before)
    monkeypatch.setattr(simulation, "_completed_run_base", lambda *_: base)
    load_store = Mock(side_effect=AssertionError("Ambiguous uploads must be rejected before analysis"))
    monkeypatch.setattr(simulation, "load_run_store", load_store)
    with TestClient(app, raise_server_exceptions=False) as client:
        response = client.post("/api/projects/proj_test/runs/run_test/fidelity", files={
            "file": (f"pos.{extension}", data(headers, [values], extension), "application/octet-stream"),
        })
    assert response.status_code == 400, response.text
    assert "duplicate column" in response.json()["detail"]
    assert saved.read_bytes() == before
    load_store.assert_not_called()
