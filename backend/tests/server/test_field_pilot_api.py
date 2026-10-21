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
    review = client.post(f"{ROOT}/staff-pilots/{pid}/observations/preview", files={"file": ("observations.csv", data, "text/csv")}, data={"revision": str(revision)})
    if review.status_code != 200:
        return review
    return client.put(f"{ROOT}/staff-pilots/{pid}/observations", files={"file": ("observations.csv", data, "text/csv")},
                      data={"revision": str(revision), "review_token": review.json()["review_token"], "reason": "Offline test import"})


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
    assert len(client.get(f"{ROOT}/staff-pilots/{pid}").json()["pilot"]["import_history"]) == 1


def test_unknown_project_and_pilot_ids_and_upload_limit(client):
    assert client.get("/api/projects/missing/staff-pilots").status_code == 404
    assert client.get(f"{ROOT}/staff-pilots/missing").status_code == 404
    assert client.post(f"{ROOT}/staff-pitches/missing/pilots", json={
        "name": "No source", "eligibility": "all", "outcome_window": "today", "blocks": [{"staff_id": "s", "shift_id": "a", "encounters": 40}],
    }).status_code == 404
    pid = create(client)["pilot"]["pilot_id"]
    assert upload(client, pid, b"x" * (2 * 1024 * 1024 + 1)).status_code == 413
    assert client.get(f"{ROOT}/staff-pilots/{pid}").json()["pilot"]["revision"] == 0


def test_sample_planning_preview_and_saved_assessment_use_actual_fixed_design(client, tmp_path):
    assumptions = {"minimum_effect": 0.2, "target_power": 0.8, "eligible_per_day": 30, "available_days": 14}
    preview = client.post(f"{ROOT}/staff-pilots/plan", json={"assumptions": assumptions, "block_counts": [100]})
    assert preview.status_code == 200, preview.text
    plan = preview.json()
    assert plan["required_encounters"] == 510 and plan["required_days"] == 17
    assert client.get(f"{ROOT}/staff-pilots").json() == []  # preview is side-effect free
    created = client.post(f"{ROOT}/staff-pitches/pit_test/pilots", json={
        "name": "Planned tea", "eligibility": "Each customer once", "outcome_window": "Same visit",
        "blocks": [{"staff_id": "s1", "shift_id": "day1", "encounters": 510}], "planning": assumptions,
    })
    assert created.status_code == 200, created.text
    saved = created.json()["pilot"]
    assert saved["planning"]["planned_encounters"] == 510  # never accept the old preview's 100
    assert saved["planning"]["planned_power_lower_bound"] >= 0.8
    pid = saved["pilot_id"]
    assert upload(client, pid, sheet(client, pid, complete=True)).status_code == 200
    closed = client.post(f"{ROOT}/staff-pilots/{pid}/close", json={"revision": 1}).json()
    assert closed["pilot"]["planning"] == saved["planning"]
    assert 1 - closed["analysis"]["ci_low"] == pytest.approx(saved["planning"]["planned_ci_half_width"])
    assert client.get(f"{ROOT}/staff-pilots/{pid}").json()["pilot"]["planning"] == saved["planning"]


def test_planning_validates_project_and_assumptions_and_reads_legacy_pilots(client, tmp_path):
    payload = {"assumptions": {"minimum_effect": 0.05, "target_power": 0.8, "eligible_per_day": 20, "available_days": 30}, "block_counts": [100]}
    assert client.post("/api/projects/missing/staff-pilots/plan", json=payload).status_code == 404
    payload["assumptions"]["minimum_effect"] = 0
    assert client.post(f"{ROOT}/staff-pilots/plan", json=payload).status_code == 422
    pid = create(client)["pilot"]["pilot_id"]
    path = tmp_path / ".data" / PID / "marketing" / "field-pilots" / pid / "pilot.json"
    legacy = read_json(path)
    legacy.pop("planning", None)
    legacy["design"].pop("planning", None)
    write_json(path, legacy)
    response = client.get(f"{ROOT}/staff-pilots/{pid}")
    assert response.status_code == 200 and response.json()["pilot"]["planning"] is None


def preview_import(client, pid, data, revision=0):
    return client.post(f"{ROOT}/staff-pilots/{pid}/observations/preview", files={"file": ("sheet.csv", data)}, data={"revision": str(revision)})


def apply_import(client, pid, data, preview, reason="Verified source records"):
    return client.put(f"{ROOT}/staff-pilots/{pid}/observations", files={"file": ("sheet.csv", data)},
                      data={"revision": str(preview["revision"]), "review_token": preview["review_token"], "reason": reason})


def test_review_is_readonly_and_apply_requires_exact_review_and_reason(client, tmp_path):
    pid = create(client)["pilot"]["pilot_id"]
    path = tmp_path / ".data" / PID / "marketing" / "field-pilots" / pid / "pilot.json"
    original = path.read_bytes()
    data = sheet(client, pid, complete=True)
    review = preview_import(client, pid, data).json()
    assert review["summary"]["changed_assignments"] == 40 and len(review["changes"]) == 120
    assert path.read_bytes() == original and not (path.parent / "imports").exists()
    assert client.put(f"{ROOT}/staff-pilots/{pid}/observations", files={"file": ("x.csv", data)}, data={"revision": "0"}).status_code == 422
    assert apply_import(client, pid, data + b"\n", review).status_code in (400, 409)
    assert apply_import(client, pid, sheet(client, pid), review).status_code == 409
    assert apply_import(client, pid, data, {**review, "review_token": "0" * 64}).status_code == 409
    assert apply_import(client, pid, data, review, reason="   ").status_code == 400
    assert path.read_bytes() == original
    saved = apply_import(client, pid, data, review)
    assert saved.status_code == 200, saved.text
    history = saved.json()["pilot"]["import_history"]
    assert len(history) == 1 and history[0]["revision"] == 1 and history[0]["summary"] == review["summary"]
    audit = client.get(f"{ROOT}/staff-pilots/{pid}/imports/1").json()
    assert audit["changes"] == review["changes"] and audit["record"] == history[0]
    assert apply_import(client, pid, data, review).status_code == 409
    noop = preview_import(client, pid, data, 1).json()
    assert noop["summary"]["changed_fields"] == 0
    assert apply_import(client, pid, data, noop).json()["pilot"]["revision"] == 1
    assert len(client.get(f"{ROOT}/staff-pilots/{pid}").json()["pilot"]["import_history"]) == 1
    assert client.post(f"{ROOT}/staff-pilots/{pid}/close", json={"revision": 1}).status_code == 200
    assert client.get(f"{ROOT}/staff-pilots/{pid}/imports/1").json() == audit
    rows = list(csv.DictReader(io.StringIO(client.get(f"{ROOT}/staff-pilots/{pid}/imports.csv").text)))
    assert len(rows) == 120 and rows[0]["reason"] == "Verified source records"
    assert client.get(f"{ROOT}/staff-pilots/{pid}/imports/2").status_code == 404


def test_corrections_preserve_prior_values_and_legacy_history_boundary(client, tmp_path):
    pid = create(client)["pilot"]["pilot_id"]
    assert upload(client, pid, sheet(client, pid, complete=True)).status_code == 200
    path = tmp_path / ".data" / PID / "marketing" / "field-pilots" / pid / "pilot.json"
    legacy = read_json(path); legacy.pop("history_start_revision"); legacy.pop("import_history")
    write_json(path, legacy)
    assert client.get(f"{ROOT}/staff-pilots/{pid}").json()["pilot"]["history_start_revision"] is None
    assert client.get(f"{ROOT}/staff-pilots/{pid}/imports/1").status_code == 404
    rows = list(csv.DictReader(io.StringIO(sheet(client, pid).decode())))
    rows[0]["purchased"] = "0" if rows[0]["purchased"] == "1" else "1"
    rows[1]["purchased"] = ""
    out = io.StringIO(); writer = csv.DictWriter(out, fieldnames=list(rows[0])); writer.writeheader(); writer.writerows(rows)
    data = out.getvalue().encode(); review = preview_import(client, pid, data, 1).json()
    assert review["summary"]["purchase_reversals"] == 1 and review["summary"]["cleared_values"] == 1
    saved = apply_import(client, pid, data, review, reason="=Verified correction").json()
    assert saved["pilot"]["history_start_revision"] == 1
    assert [r["revision"] for r in saved["pilot"]["import_history"]] == [2]
    assert saved["analysis"]["a"]["missing_outcomes"] + saved["analysis"]["b"]["missing_outcomes"] == 1
    assert saved["analysis"]["ci_low"] is None
    exported = list(csv.DictReader(io.StringIO(client.get(f"{ROOT}/staff-pilots/{pid}/imports.csv").text)))
    assert len(exported) == 2 and exported[0]["reason"] == "'=Verified correction"
    (path.parent / "imports" / "2.json").unlink()
    assert client.get(f"{ROOT}/staff-pilots/{pid}/imports.csv").status_code == 409


def test_failed_atomic_commit_does_not_publish_history_or_change_observations(client, tmp_path, monkeypatch):
    from store_emulator.application import field_pilot
    pid = create(client)["pilot"]["pilot_id"]
    path = tmp_path / ".data" / PID / "marketing" / "field-pilots" / pid / "pilot.json"
    before = path.read_bytes(); data = sheet(client, pid, complete=True); review = preview_import(client, pid, data).json()
    real_write = field_pilot.write_json

    def fail_commit(target, value):
        if target.name == "pilot.json":
            raise OSError("Simulated disk failure")
        real_write(target, value)

    with monkeypatch.context() as patch:
        patch.setattr(field_pilot, "write_json", fail_commit)
        with pytest.raises(OSError, match="Simulated disk failure"):
            apply_import(client, pid, data, review)
    assert path.read_bytes() == before
    assert client.get(f"{ROOT}/staff-pilots/{pid}/imports/1").status_code == 404
    assert apply_import(client, pid, data, review).status_code == 200
    assert len(client.get(f"{ROOT}/staff-pilots/{pid}").json()["pilot"]["import_history"]) == 1
