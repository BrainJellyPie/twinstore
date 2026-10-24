"""Reject corrupt CSV text before replacing previous POS evidence."""

from unittest.mock import Mock

from fastapi.testclient import TestClient
import pytest

from store_emulator.application import simulation
from store_emulator.server.main import app


@pytest.mark.parametrize("row", ["001\x00A,tea,1,300", "001,tea\x00other,1,300", "001,tea,1\x0099,300", "001,tea,1,3\x0000"])
def test_null_text_is_rejected_before_analysis_and_preserves_evidence(tmp_path, monkeypatch, row):
    monkeypatch.chdir(tmp_path)
    base = tmp_path / "run"
    saved = base / "output" / "fidelity.json"
    saved.parent.mkdir(parents=True)
    before = b'{"previous_evidence": true}\n'
    saved.write_bytes(before)
    monkeypatch.setattr(simulation, "_completed_run_base", lambda *_: base)
    load_store = Mock(side_effect=AssertionError("NUL text must fail before analysis"))
    monkeypatch.setattr(simulation, "load_run_store", load_store)
    content = ("receipt_id,sku,quantity,unit_price\n" + row + "\n").encode()
    with TestClient(app, raise_server_exceptions=False) as client:
        response = client.post("/api/projects/proj_test/runs/run_test/fidelity", files={
            "file": ("pos.csv", content, "text/csv"),
        })
    assert response.status_code == 400, response.text
    assert "NUL" in response.json()["detail"]
    assert saved.read_bytes() == before
    load_store.assert_not_called()
