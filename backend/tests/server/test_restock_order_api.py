import csv
import io

import pytest
from fastapi.testclient import TestClient

from store_emulator.application.storage.io import read_json, write_json
from store_emulator.application.storage.setups import metadata_path
from store_emulator.domain.shelf_lab import AuditFinding, AuditReport, LabJobStatus

PID = "proj_67916afd"
CID = "cap_test"
JID = "aud_test"
ROOT = f"/api/projects/{PID}/captures/{CID}/lab/jobs/{JID}/restock-order"


@pytest.fixture
def client(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    monkeypatch.setenv("TWINSTORE_LOCAL_VLM_AUTO", "0")
    from store_emulator.server.main import app
    with TestClient(app) as client:
        folder = tmp_path / ".data" / PID / "captures" / CID / "lab" / "jobs" / JID
        write_json(folder / "status.json", LabJobStatus(job_id=JID, capture_id=CID, kind="audit", status="completed").model_dump())
        write_json(folder / "report.json", AuditReport(job_id=JID, capture_id=CID, setup_id="setup_test", rack_id="rack",
                   face="N", currency="USD", compliance=0, findings=[AuditFinding(kind="missing", level=1, sku="tea", name="Tea")]).model_dump())
        yield client, folder


def request():
    return {"currency": "USD", "budget_minor": 1000, "delivery_fee_minor": 100,
            "items": [{"sku": "tea", "required_units": 10, "stockroom_units": 1, "pack_size": 6,
                       "pack_cost_minor": 300, "max_packs": 5, "priority": 1}]}


def test_preview_and_export_use_the_saved_audit_without_writing_or_running_a_model(client):
    api, folder = client
    before = {p.name: p.read_bytes() for p in folder.iterdir()}
    response = api.post(ROOT, json=request())
    assert response.status_code == 200, response.text
    plan = response.json()
    assert plan["audit_id"] == JID and plan["total_cost_minor"] == 700 and plan["remaining_budget_minor"] == 300
    assert plan["actions"][0]["surplus_units"] == 3
    exported = api.post(ROOT + ".csv", json=request())
    assert exported.status_code == 200 and "attachment" in exported.headers["content-disposition"]
    assert list(csv.DictReader(io.StringIO(exported.text)))[0]["total_cost_minor"] == "700"
    assert {p.name: p.read_bytes() for p in folder.iterdir()} == before


def test_invalid_quantities_currency_and_source_ids_do_not_produce_plans(client):
    api, _ = client
    for field, value in (("pack_size", 0), ("stockroom_units", True), ("max_packs", 1.5)):
        data = request(); data["items"][0][field] = value
        assert api.post(ROOT, json=data).status_code == 422
    data = request(); data["currency"] = "KRW"
    assert api.post(ROOT, json=data).status_code == 400
    data = request(); data["items"][0]["sku"] = "other"
    assert api.post(ROOT, json=data).status_code == 400
    assert api.post(ROOT.replace(JID, "missing"), json=request()).status_code == 404
    assert api.post(ROOT.replace(PID, "missing"), json=request()).status_code == 404


def test_incomplete_mismatched_and_orphaned_audits_cannot_generate_orders(client):
    api, folder = client
    status = read_json(folder / "status.json"); status["status"] = "running"
    write_json(folder / "status.json", status)
    assert api.post(ROOT, json=request()).status_code == 409
    status["status"] = "completed"; write_json(folder / "status.json", status)
    report = read_json(folder / "report.json"); report["capture_id"] = "cap_other"
    write_json(folder / "report.json", report)
    assert api.post(ROOT, json=request()).status_code == 409
    metadata_path(PID).unlink()
    assert api.post(ROOT, json=request()).status_code == 404
