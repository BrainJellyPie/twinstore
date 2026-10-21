import pytest
from fastapi.testclient import TestClient

from store_emulator.application.storage.setups import metadata_path

PID = "proj_67916afd"
ROOT = f"/api/projects/{PID}/protocols"
PLAN = {"title": "Offline study", "evidence_type": "synthetic", "question": "Hypothesis", "population": "Saved cohort", "design": "Paired fixed design",
    "primary_outcome": "Any purchase", "analysis_unit": "Shopper", "planned_sample_size": 60, "exclusions_and_missing": "No missing imputation",
    "stopping_rule": "Fixed sample", "analysis_plan": "Paired contrasts with multiplicity adjustment"}
CREATE = {"request_id": "a" * 32, "plan": PLAN, "data_stage": "not_collected"}


@pytest.fixture
def client(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path); monkeypatch.setenv("TWINSTORE_LOCAL_VLM_AUTO", "0")
    from store_emulator.server.main import app
    with TestClient(app) as client: yield client


def test_create_read_amend_list_and_head_bound_exports(client):
    metadata = metadata_path(PID).read_bytes()
    assert client.get(ROOT).json() == {"protocols": [], "unavailable_ids": []}
    created = client.post(ROOT, json=CREATE); assert created.status_code == 200, created.text
    first = created.json(); id = first["ledger"]["protocol_id"]
    assert client.get(f"{ROOT}/{id}").json() == first
    amendment = {"expected_head": first["head_sha256"], "plan": {**PLAN, "planned_sample_size": 80}, "data_stage": "collected_unseen", "reason": "Recruitment change before outcomes"}
    response = client.post(f"{ROOT}/{id}/amendments", json=amendment); assert response.status_code == 200, response.text
    current = response.json(); assert current["planned_sample_delta"] == 20
    assert current["ledger"]["revisions"][0] == first["ledger"]["revisions"][0]
    assert client.get(ROOT).json()["protocols"][0]["revision"] == 2
    for suffix in ["export.json", "changes.csv"]:
        output = client.get(f"{ROOT}/{id}/{suffix}", params={"head": current["head_sha256"]})
        assert output.status_code == 200 and "attachment" in output.headers["content-disposition"]
        if suffix == "export.json": assert output.json() == current
    assert metadata_path(PID).read_bytes() == metadata


def create(client, token="a" * 32):
    response = client.post(ROOT, json={**CREATE, "request_id": token})
    assert response.status_code == 200, response.text
    return response.json()


def amend_request(view, **changes):
    return {"expected_head": view["head_sha256"], "plan": {**PLAN, "planned_sample_size": 80}, "data_stage": "collected_unseen", "reason": "Revised before outcomes", **changes}


def test_idempotent_create_stale_revision_and_stage_reversal(client):
    first = create(client); id = first["ledger"]["protocol_id"]
    assert create(client) == first
    assert client.post(ROOT, json={**CREATE, "plan": {**PLAN, "title": "Different"}}).status_code == 409
    current = client.post(f"{ROOT}/{id}/amendments", json=amend_request(first, data_stage="results_seen")).json()
    assert create(client) == current  # Lost create reply cannot roll back later amendments.
    assert len(client.get(ROOT).json()["protocols"]) == 1
    assert client.post(f"{ROOT}/{id}/amendments", json=amend_request(first)).status_code == 409
    assert client.post(f"{ROOT}/{id}/amendments", json=amend_request(current)).status_code == 422
    for suffix in ["export.json", "changes.csv"]:
        assert client.get(f"{ROOT}/{id}/{suffix}", params={"head": first["head_sha256"]}).status_code == 409
        assert client.get(f"{ROOT}/{id}/{suffix}", params={"head": "bad"}).status_code == 422
    assert client.get(f"{ROOT}/{id}").json() == current


def test_invalid_json_scope_and_deleted_project(client):
    for req in [{}, {**CREATE, "extra": 1}, {**CREATE, "data_stage": "unknown"}, {**CREATE, "request_id": "../x"},
        {**CREATE, "plan": {**PLAN, "planned_sample_size": False}}, {**CREATE, "plan": {**PLAN, "analysis_plan": ""}}]:
        assert client.post(ROOT, json=req).status_code == 422
    first = create(client); id = first["ledger"]["protocol_id"]
    assert client.get(ROOT + "/invalid-id").status_code == 400
    assert client.get(ROOT + "/protocol_" + "f" * 32).status_code == 404
    assert client.post(f"{ROOT}/{id}/amendments", json=amend_request(first, plan=PLAN, data_stage="not_collected")).status_code == 422
    for reason in [" ", "x" * 1001, "\x00"]:
        assert client.post(f"{ROOT}/{id}/amendments", json=amend_request(first, reason=reason)).status_code == 422
    metadata_path(PID).unlink()
    assert client.get(ROOT).status_code == 404
    assert client.post(ROOT, json=CREATE).status_code == 404
    assert client.post(f"{ROOT}/{id}/amendments", json=amend_request(first)).status_code == 404
    assert client.get(f"{ROOT}/{id}/export.json", params={"head": first["head_sha256"]}).status_code == 404


def test_corrupt_oversized_or_misidentified_history_is_isolated(client, tmp_path):
    import json
    first = create(client); other = create(client, "b" * 32); id = first["ledger"]["protocol_id"]
    path = tmp_path / ".data" / PID / "marketing" / "protocols" / f"{id}.json"
    original = path.read_bytes()
    identity = json.loads(original); identity["protocol_id"] = other["ledger"]["protocol_id"]
    changed = json.loads(original); changed["revisions"][0]["plan"]["question"] = "Changed without hash"
    for content in [b"{", b"x" * (4 * 1024 * 1024 + 1), json.dumps(identity).encode(), json.dumps(changed).encode()]:
        path.write_bytes(content)
        assert client.get(f"{ROOT}/{id}").status_code == 409
        assert client.post(f"{ROOT}/{id}/amendments", json=amend_request(first)).status_code == 409
        assert client.get(f"{ROOT}/{id}/changes.csv", params={"head": first["head_sha256"]}).status_code == 409
        listing = client.get(ROOT).json()
        assert listing["unavailable_ids"] == [id] and len(listing["protocols"]) == 1
        assert path.read_bytes() == content
    path.write_bytes(original)
    assert client.get(f"{ROOT}/{id}").json() == first


def test_parallel_amendments_have_one_winner_and_preserve_original(client):
    from concurrent.futures import ThreadPoolExecutor
    from threading import Barrier
    first = create(client); id = first["ledger"]["protocol_id"]; barrier = Barrier(2)
    def submit(count):
        barrier.wait()
        return client.post(f"{ROOT}/{id}/amendments", json=amend_request(first, plan={**PLAN, "planned_sample_size": count}))
    with ThreadPoolExecutor(max_workers=2) as pool:
        responses = list(pool.map(submit, [80, 90]))
    assert sorted(r.status_code for r in responses) == [200, 409]
    latest = client.get(f"{ROOT}/{id}").json()
    assert len(latest["ledger"]["revisions"]) == 2 and latest["ledger"]["revisions"][0] == first["ledger"]["revisions"][0]
    assert latest["ledger"]["revisions"][-1]["plan"]["planned_sample_size"] in [80, 90]


def test_cross_process_lock_is_respected(client, tmp_path):
    import json
    import subprocess
    import sys
    from filelock import FileLock
    first = create(client); id = first["ledger"]["protocol_id"]
    lock_path = tmp_path / ".data" / PID / "marketing" / "protocols" / ".update.lock"
    code = """
import json,sys
from store_emulator.application.protocols import amend_protocol
from store_emulator.application.errors import AppError
from store_emulator.domain.protocols import AmendProtocol
try:
    amend_protocol(sys.argv[1],sys.argv[2],AmendProtocol.model_validate_json(sys.argv[3]))
except AppError as e:
    print(e.status_code)
"""
    with FileLock(lock_path, timeout=0):
        completed = subprocess.run([sys.executable, "-c", code, PID, id, json.dumps(amend_request(first))], cwd=tmp_path, capture_output=True, text=True, timeout=30)
    assert completed.returncode == 0, completed.stderr
    assert completed.stdout.strip() == "409"
    assert client.get(f"{ROOT}/{id}").json() == first


def test_atomic_write_failure_keeps_the_previous_history_and_retry_succeeds(client, tmp_path, monkeypatch):
    from store_emulator.application.storage import io
    first = create(client); id = first["ledger"]["protocol_id"]
    path = tmp_path / ".data" / PID / "marketing" / "protocols" / f"{id}.json"
    original = path.read_bytes()
    def fail(*args): raise OSError("simulated disk failure")
    with monkeypatch.context() as context:
        context.setattr(io.os, "replace", fail)
        assert client.post(f"{ROOT}/{id}/amendments", json=amend_request(first)).status_code == 500
    assert path.read_bytes() == original and not list(path.parent.glob("*.tmp-*"))
    assert client.post(f"{ROOT}/{id}/amendments", json=amend_request(first)).status_code == 200


def test_max_revision_and_project_record_limits_allow_existing_idempotent_retries(client):
    from store_emulator.application import protocols
    from store_emulator.domain.protocols import AmendProtocol, CreateProtocol
    first = protocols.create_protocol(PID, CreateProtocol.model_validate(CREATE))
    id = first.ledger.protocol_id; current = first
    for count in range(2, 51):
        current = protocols.amend_protocol(PID, id, AmendProtocol.model_validate({"expected_head": current.head_sha256,
            "plan": {**PLAN, "planned_sample_size": count}, "data_stage": "not_collected", "reason": f"Revision {count}"}))
    assert len(current.ledger.revisions) == 50
    assert client.post(f"{ROOT}/{id}/amendments", json=amend_request(current.model_dump(mode="json"))).status_code == 409
    for token in range(99):
        protocols.create_protocol(PID, CreateProtocol.model_validate({**CREATE, "request_id": f"{token:032x}"}))
    assert len(client.get(ROOT).json()["protocols"]) == 100
    assert client.post(ROOT, json={**CREATE, "request_id": "c" * 32}).status_code == 409
    assert client.post(ROOT, json=CREATE).status_code == 200


def test_sample_unit_change_withholds_delta_in_api_and_export(client):
    first = create(client); id = first["ledger"]["protocol_id"]
    response = client.post(f"{ROOT}/{id}/amendments", json=amend_request(first, plan={**PLAN, "analysis_unit": "Store", "planned_sample_size": 80}))
    assert response.status_code == 200
    assert response.json()["planned_sample_delta"] is None
    export = client.get(f"{ROOT}/{id}/export.json", params={"head": response.json()["head_sha256"]})
    assert export.json()["planned_sample_delta"] is None
