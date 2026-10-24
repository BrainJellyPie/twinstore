"""Customer generation cannot silently omit damaged retained source evidence."""

from pathlib import Path
from unittest.mock import Mock

import pytest
from fastapi.testclient import TestClient

from store_emulator.application import generation_async
from store_emulator.application.storage.generations import list_generations
from store_emulator.application.storage.io import read_json, write_json
from store_emulator.application.storage.setups import metadata_path, personas_path
from store_emulator.server.main import app
from tests.server.test_simulation_setup_races import PID, SID, layout

DATA = b"date,hour,visitors\n2026-10-19,9,12\n"


@pytest.mark.parametrize("damage", ["missing_metadata", "invalid_json", "wrong_shape", "missing_name",
                                   "missing_data", "empty_data", "changed_data", "extra_data", "unreadable"])
def test_retry_rejects_damaged_customer_evidence_before_queueing(layout, monkeypatch, damage):
    submit = Mock()
    monkeypatch.setattr(generation_async.executor, "submit", submit)
    generation_async._keep_upload(PID, DATA, "고객.csv")
    folder = metadata_path(PID).parent / "supplemental"
    receipt = folder / "upload.json"
    source = folder / "upload.csv"
    if damage == "missing_metadata":
        receipt.unlink()
    elif damage == "invalid_json":
        receipt.write_text("{broken")
    elif damage == "wrong_shape":
        write_json(receipt, [])
    elif damage == "missing_name":
        write_json(receipt, {})
    elif damage == "missing_data":
        source.unlink()
    elif damage == "empty_data":
        source.write_bytes(b"")
    elif damage == "changed_data":
        source.write_bytes(DATA.replace(b",12", b",99"))
    elif damage == "extra_data":
        (folder / "upload.xlsx").write_bytes(b"ambiguous evidence")
    else:
        original = Path.read_bytes

        def denied(path):
            if path == source:
                raise PermissionError("offline source unavailable")
            return original(path)

        monkeypatch.setattr(Path, "read_bytes", denied)
    before = read_json(personas_path(PID))
    client = TestClient(app, raise_server_exceptions=False)
    response = client.post(f"/api/projects/{PID}/setups/{SID}/regenerate-persona")
    assert response.status_code == 409, response.text
    assert "uploaded customer data" in response.json()["detail"].lower()
    submit.assert_not_called()
    assert list_generations(PID) == []
    assert read_json(personas_path(PID)) == before


@pytest.mark.parametrize("legacy", [False, True])
def test_intact_customer_upload_is_passed_to_retry(layout, monkeypatch, legacy):
    submit = Mock()
    monkeypatch.setattr(generation_async.executor, "submit", submit)
    generation_async._keep_upload(PID, DATA, "고객.CSV")
    if legacy:
        write_json(metadata_path(PID).parent / "supplemental/upload.json", {"filename": "고객.CSV"})
    client = TestClient(app, raise_server_exceptions=False)
    response = client.post(f"/api/projects/{PID}/setups/{SID}/regenerate-persona")
    assert response.status_code == 200, response.text
    assert submit.call_args.kwargs["supplemental_bytes"] == DATA
    assert submit.call_args.kwargs["supplemental_filename"] == "고객.CSV"
