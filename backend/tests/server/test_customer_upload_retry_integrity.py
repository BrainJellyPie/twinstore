"""Customer generation cannot silently omit damaged retained source evidence."""

import json
import shutil
from pathlib import Path
from unittest.mock import Mock

import pytest
from fastapi.testclient import TestClient

from store_emulator.application import generation_async
from store_emulator.application.errors import AppError
from store_emulator.application.storage.generations import list_generations
from store_emulator.application.storage.io import read_json, write_json
from store_emulator.application.storage.setups import metadata_path, personas_path
from store_emulator.domain.config import SimulationConfig
from store_emulator.server.main import app
from tests.server.test_project_templates import _meta
from tests.server.test_simulation_setup_races import PID, SID, layout

DATA = b"date,hour,visitors\n2026-10-19,9,12\n"


@pytest.mark.parametrize("damage", ["missing_folder", "missing_metadata", "invalid_json", "wrong_shape", "missing_name",
                                   "missing_data", "empty_data", "changed_data", "extra_data", "unreadable"])
def test_retry_rejects_damaged_customer_evidence_before_queueing(layout, monkeypatch, damage):
    submit = Mock()
    monkeypatch.setattr(generation_async.executor, "submit", submit)
    generation_async._keep_upload(PID, DATA, "고객.csv")
    folder = metadata_path(PID).parent / "supplemental"
    receipt = folder / "upload.json"
    source = folder / "upload.csv"
    if damage == "missing_folder":
        shutil.rmtree(folder)
    elif damage == "missing_metadata":
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
        meta = read_json(metadata_path(PID))
        meta.pop("supplemental_upload_expected")
        write_json(metadata_path(PID), meta)
    client = TestClient(app, raise_server_exceptions=False)
    response = client.post(f"/api/projects/{PID}/setups/{SID}/regenerate-persona")
    assert response.status_code == 200, response.text
    assert submit.call_args.kwargs["supplemental_bytes"] == DATA
    assert submit.call_args.kwargs["supplemental_filename"] == "고객.CSV"
    assert read_json(metadata_path(PID))["supplemental_upload_expected"] is True
    if legacy:
        shutil.rmtree(metadata_path(PID).parent / "supplemental")
        with pytest.raises(AppError) as missing:
            generation_async._kept_upload(PID)
        assert missing.value.status_code == 409


@pytest.mark.parametrize("stage", ["metadata", "directory", "data", "receipt"])
def test_upload_persistence_failure_does_not_queue_customer_writing(layout, monkeypatch, stage):
    submit = Mock()
    monkeypatch.setattr(generation_async.executor, "submit", submit)
    folder = metadata_path(PID).parent / "supplemental"
    before = personas_path(PID).read_bytes()
    original_json = generation_async.write_json
    original_mkdir = Path.mkdir
    original_bytes = Path.write_bytes

    def fail_json(path, data):
        if path == (metadata_path(PID) if stage == "metadata" else folder / "upload.json"):
            raise OSError("Offline customer evidence save failure")
        original_json(path, data)

    def fail_mkdir(path, *args, **kwargs):
        if path == folder:
            raise OSError("Offline customer evidence save failure")
        return original_mkdir(path, *args, **kwargs)

    def fail_bytes(path, data):
        if path.parent == folder:
            raise OSError("Offline customer evidence save failure")
        return original_bytes(path, data)

    with monkeypatch.context() as failure:
        if stage in {"metadata", "receipt"}:
            failure.setattr(generation_async, "write_json", fail_json)
        elif stage == "directory":
            failure.setattr(Path, "mkdir", fail_mkdir)
        else:
            failure.setattr(Path, "write_bytes", fail_bytes)
        with pytest.raises(AppError) as caught:
            generation_async.start_persona_generation(SimulationConfig(), PID, SID,
                                                     supplemental_bytes=DATA, supplemental_filename="customers.csv")
    assert caught.value.status_code == 503
    submit.assert_not_called()
    assert list_generations(PID) == []
    assert personas_path(PID).read_bytes() == before
    if stage != "metadata":
        response = TestClient(app, raise_server_exceptions=False).post(f"/api/projects/{PID}/setups/{SID}/regenerate-persona")
        assert response.status_code == 409, response.text
        submit.assert_not_called()
    generation_async.start_persona_generation(SimulationConfig(), PID, SID,
                                             supplemental_bytes=DATA, supplemental_filename="customers.csv")
    submit.assert_called_once()
    assert submit.call_args.kwargs["supplemental_bytes"] == DATA


@pytest.mark.parametrize("has_upload", [False, True])
def test_new_project_records_whether_upload_evidence_is_required(layout, monkeypatch, has_upload):
    submit = Mock()
    monkeypatch.setattr(generation_async.executor, "submit", submit)
    client = TestClient(app, raise_server_exceptions=False)
    files = {"supplemental": ("customers.csv", DATA, "text/csv")} if has_upload else None
    response = client.post("/api/projects/create-store", data={"meta": json.dumps(_meta())}, files=files)
    assert response.status_code == 200, response.text
    pid = response.json()["metadata"]["project_id"]
    assert read_json(metadata_path(pid))["supplemental_upload_expected"] is has_upload
    assert submit.call_args.kwargs["supplemental_bytes"] == (DATA if has_upload else None)


def test_failed_new_store_upload_cannot_later_retry_without_its_evidence(layout, monkeypatch):
    submit = Mock()
    monkeypatch.setattr(generation_async.executor, "submit", submit)
    monkeypatch.setattr(generation_async, "_keep_upload", Mock(side_effect=AppError("Offline storage unavailable", 503)))
    client = TestClient(app, raise_server_exceptions=False)
    response = client.post("/api/projects/create-store", data={"meta": json.dumps(_meta())},
                           files={"supplemental": ("customers.csv", DATA, "text/csv")})
    assert response.status_code == 503, response.text
    roots = [p for p in metadata_path(PID).parent.parent.iterdir() if p.is_dir() and p.name.startswith("proj_") and p.name != PID]
    assert len(roots) == 1
    pid = roots[0].name
    assert read_json(metadata_path(pid))["supplemental_upload_expected"] is True
    setups = list((roots[0] / "setups").glob("*.json"))
    assert len(setups) == 1
    response = client.post(f"/api/projects/{pid}/setups/{setups[0].stem}/regenerate-persona")
    assert response.status_code == 409, response.text
    submit.assert_not_called()
    assert list_generations(pid) == []
