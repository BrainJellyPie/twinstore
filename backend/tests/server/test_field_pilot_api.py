import csv
import io
from concurrent.futures import ThreadPoolExecutor

import pytest
from fastapi.testclient import TestClient
from filelock import FileLock

from store_emulator.application.storage.io import read_json, write_json
from store_emulator.domain.marketing import JobStatus
from store_emulator.domain.staff_pitch import PitchProduct, PitchReport, PitchRequest

PID = "proj_67916afd"
ROOT = f"/api/projects/{PID}"


@pytest.fixture
def client(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    monkeypatch.setenv("TWINSTORE_LOCAL_VLM_AUTO", "0")
    from store_emulator.server.main import app
    with TestClient(app) as c:
        req = PitchRequest(setup_id="setup_7d6d", sku="tea", context="Browsing tea", variants=(
            {"name": "Current", "script": "Hello"}, {"name": "New", "script": "Can I help?"}))
        report = PitchReport(pitch_id="pit_test", name="Tea", model="offline fixture", request=req,
                             product=PitchProduct(sku="tea", name="Tea", price=2000, currency="KRW"), attempted=20, pairs=20,
                             excluded=0, comparisons=[], segments=[], screening_leader=None, recommendation="", answers=[], notes=[])
        folder = tmp_path / ".data" / PID / "marketing" / "pitches" / "pit_test"
        write_json(folder / "status.json", JobStatus(job_id="pit_test", kind="pitch", status="completed").model_dump())
        write_json(folder / "report.json", report.model_dump(mode="json"))
        yield c


def create(client):
    response = client.post(f"{ROOT}/staff-pitches/pit_test/pilots", json={
        "name": "Field tea", "eligibility": "First eligible tea encounter", "outcome_window": "Same visit",
        "blocks": [{"staff_id": "staff1", "shift_id": "day1_am", "encounters": 40}], "seed": 5,
    })
    assert response.status_code == 200, response.text
    return response.json()


def sheet(client, pid, *, complete=False):
    response = client.get(f"{ROOT}/staff-pilots/{pid}/observations.csv")
    assert response.status_code == 200
    rows = list(csv.DictReader(io.StringIO(response.text)))
    if complete:
        for row in rows:
            row.update(enrolled="1", delivered="0", purchased="1" if row["arm"] == "B" else "0")
    out = io.StringIO(); writer = csv.DictWriter(out, fieldnames=list(rows[0])); writer.writeheader(); writer.writerows(rows)
    return out.getvalue().encode()


def upload(client, pid, data, revision=0):
    return client.put(f"{ROOT}/staff-pilots/{pid}/observations", files={"file": ("observations.csv", data, "text/csv")}, data={"revision": str(revision)})


def test_end_to_end_observed_pilot_and_locked_results(client, tmp_path):
    created = create(client)
    pid = created["pilot"]["pilot_id"]
    assert created["analysis"]["a"]["planned"] == created["analysis"]["b"]["planned"] == 20
    assert client.get(f"{ROOT}/staff-pilots").json()[0]["pilot_id"] == pid
    assert client.post(f"{ROOT}/staff-pilots/{pid}/close", json={"revision": 0}).status_code == 409
    result = upload(client, pid, sheet(client, pid, complete=True))
    assert result.status_code == 200, result.text
    assert result.json()["analysis"]["target_completed"] and result.json()["analysis"]["ci_low"] is None
    assert result.json()["analysis"]["b"]["not_delivered"] == 20
    closed = client.post(f"{ROOT}/staff-pilots/{pid}/close", json={"revision": 1})
    assert closed.status_code == 200 and closed.json()["analysis"]["difference"] == 1
    assert closed.json()["analysis"]["ci_low"] > 0
    assert upload(client, pid, sheet(client, pid), revision=2).status_code == 409
    assert client.post(f"{ROOT}/staff-pilots/{pid}/close", json={"revision": 2}).status_code == 409
    # The saved field experiment survives deletion of the synthetic screening job.
    assert client.delete(f"{ROOT}/staff-pitches/pit_test").status_code == 204
    saved = client.get(f"{ROOT}/staff-pilots/{pid}").json()
    assert saved["pilot"]["variants"][0]["script"] == "Hello" and saved["pilot"]["product"]["currency"] == "KRW"
    assert len(client.get(f"{ROOT}/staff-pilots").json()) == 1


def test_bad_sheet_and_stale_revision_preserve_previous_observations(client, tmp_path):
    pid = create(client)["pilot"]["pilot_id"]
    assert upload(client, pid, sheet(client, pid, complete=True)).status_code == 200
    path = tmp_path / ".data" / PID / "marketing" / "field-pilots" / pid / "pilot.json"
    before = path.read_bytes()
    assert upload(client, pid, b"bad", revision=1).status_code == 400
    assert path.read_bytes() == before
    assert upload(client, pid, sheet(client, pid), revision=0).status_code == 409
    assert path.read_bytes() == before
    with FileLock(path.with_suffix(".lock")):
        assert upload(client, pid, sheet(client, pid), revision=1).status_code == 409
    assert path.read_bytes() == before


def test_concurrent_updates_cannot_lose_a_revision(client, tmp_path):
    pid = create(client)["pilot"]["pilot_id"]
    data = sheet(client, pid, complete=True)
    with ThreadPoolExecutor(max_workers=2) as pool:
        results = list(pool.map(lambda _: upload(client, pid, data), range(2)))
    assert sorted(r.status_code for r in results) == [200, 409]
    assert client.get(f"{ROOT}/staff-pilots/{pid}").json()["pilot"]["revision"] == 1


def test_unknown_project_and_pilot_ids_and_upload_limit(client):
    assert client.get("/api/projects/missing/staff-pilots").status_code == 404
    assert client.get(f"{ROOT}/staff-pilots/missing").status_code == 404
    assert client.post(f"{ROOT}/staff-pitches/missing/pilots", json={
        "name": "No source", "eligibility": "all", "outcome_window": "today", "blocks": [{"staff_id": "s", "shift_id": "a", "encounters": 40}],
    }).status_code == 404
    pid = create(client)["pilot"]["pilot_id"]
    assert upload(client, pid, b"x" * (2 * 1024 * 1024 + 1)).status_code == 413
    assert client.get(f"{ROOT}/staff-pilots/{pid}").json()["pilot"]["revision"] == 0
