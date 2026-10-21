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


def test_collection_checks_are_readonly_refresh_after_reviewed_import_and_survive_closure(client, tmp_path):
    pid = create(client)["pilot"]["pilot_id"]
    path = tmp_path / ".data" / PID / "marketing" / "field-pilots" / pid / "pilot.json"
    before = path.read_bytes()
    initial = client.get(f"{ROOT}/staff-pilots/{pid}/collection-checks")
    assert initial.status_code == 200 and initial.json()["unrecorded_tail"] == 40 and initial.json()["tasks"] == []
    assert initial.json()["counts"]["purchase_missing_rate"] is None
    assert path.read_bytes() == before
    rows = list(csv.DictReader(io.StringIO(sheet(client, pid).decode())))
    rows[0].update(enrolled="1", delivered="0", purchased="")
    rows[2].update(enrolled="1", delivered="1", purchased="0")
    out = io.StringIO(); writer = csv.DictWriter(out, fieldnames=list(rows[0])); writer.writeheader(); writer.writerows(rows)
    assert upload(client, pid, out.getvalue().encode()).status_code == 200
    report = client.get(f"{ROOT}/staff-pilots/{pid}/collection-checks").json()
    assert report["revision"] == 1 and report["recording_gaps"] == 1 and report["unrecorded_tail"] == 37
    assert report["counts"]["missing_purchase"] == 1 and len(report["tasks"]) == 2
    assert "assignments" not in report and "purchases" not in report["counts"]
    exported = client.get(f"{ROOT}/staff-pilots/{pid}/follow-up.csv")
    assert exported.status_code == 200 and "attachment" in exported.headers["content-disposition"]
    checklist = list(csv.DictReader(io.StringIO(exported.text)))
    assert {r["issue"] for r in checklist} == {"purchase_unknown", "enrollment_gap"}
    assert {r["revision"] for r in checklist} == {"1"}
    assert upload(client, pid, sheet(client, pid, complete=True), revision=1).status_code == 200
    complete = client.get(f"{ROOT}/staff-pilots/{pid}/collection-checks").json()
    assert complete["tasks"] == [] and complete["target_completed"]
    assert client.post(f"{ROOT}/staff-pilots/{pid}/close", json={"revision": 2}).status_code == 200
    assert client.delete(f"{ROOT}/staff-pitches/pit_test").status_code == 204
    closed = client.get(f"{ROOT}/staff-pilots/{pid}/collection-checks").json()
    assert closed["revision"] == 3 and closed["finalized_at"] and closed["target_completed"]
    assert client.get(f"{ROOT}/staff-pilots/{pid}/follow-up.csv").status_code == 200


def test_collection_checks_validate_scope_and_do_not_require_new_saved_fields(client, tmp_path):
    assert client.get("/api/projects/missing/staff-pilots/missing/collection-checks").status_code == 404
    assert client.get(f"{ROOT}/staff-pilots/missing/follow-up.csv").status_code == 404
    pid = create(client)["pilot"]["pilot_id"]
    path = tmp_path / ".data" / PID / "marketing" / "field-pilots" / pid / "pilot.json"
    legacy = read_json(path)
    for key in ("history_start_revision", "import_history", "planning"):
        legacy.pop(key, None)
    write_json(path, legacy)
    assert client.get(f"{ROOT}/staff-pilots/{pid}/collection-checks").json()["counts"]["planned"] == 40


def test_pos_preview_is_readonly_and_uses_the_existing_reviewed_import_history(client, tmp_path):
    created = create(client); pid = created["pilot"]["pilot_id"]
    rows = list(csv.DictReader(io.StringIO(sheet(client, pid).decode())))
    rows[0].update(enrolled="1", delivered="0", purchased="")
    out = io.StringIO(); writer = csv.DictWriter(out, fieldnames=list(rows[0])); writer.writeheader(); writer.writerows(rows)
    assert upload(client, pid, out.getvalue().encode()).status_code == 200
    endpoint = f"{ROOT}/staff-pilots/{pid}/pos/preview"
    data = f"pilot_id,assignment_id,transaction_id,sku,net_quantity\n{pid},{rows[0]['assignment_id']},anonymous_tx,tea,2\n".encode()
    path = tmp_path / ".data" / PID / "marketing" / "field-pilots" / pid / "pilot.json"
    before = path.read_bytes(); files = sorted(path.parent.rglob("*"))
    preview = client.post(endpoint, files={"file": ("pos.csv", data)}, data={"revision": "1"})
    assert preview.status_code == 200, preview.text
    report = preview.json()
    assert report["proposed_purchases"] == 1 and report["target_sku"] == "tea"
    assert path.read_bytes() == before and sorted(path.parent.rglob("*")) == files
    assert upload(client, pid, report["candidate_csv"].encode(), revision=1).status_code == 200
    saved = client.get(f"{ROOT}/staff-pilots/{pid}").json()
    assert saved["pilot"]["assignments"][0]["purchased"] is True
    assert saved["pilot"]["assignments"][0]["delivered"] is False
    assert saved["pilot"]["revision"] == 2 and len(saved["pilot"]["import_history"]) == 2
    assert not saved["analysis"]["inference_ready"]
    assert client.post(endpoint, files={"file": ("pos.csv", data)}, data={"revision": "1"}).status_code == 409
    replay = client.post(endpoint, files={"file": ("pos.csv", data)}, data={"revision": "2"})
    assert replay.json()["proposed_purchases"] == 0
    assert upload(client, pid, report["candidate_csv"].encode(), revision=1).status_code == 409
    assert upload(client, pid, sheet(client, pid, complete=True), revision=2).status_code == 200
    assert client.post(f"{ROOT}/staff-pilots/{pid}/close", json={"revision": 3}).status_code == 200
    assert client.post(endpoint, files={"file": ("pos.csv", data)}, data={"revision": "4"}).status_code == 409


def test_pos_preview_errors_preserve_observations(client, tmp_path):
    pid = create(client)["pilot"]["pilot_id"]
    endpoint = f"{ROOT}/staff-pilots/{pid}/pos/preview"
    path = tmp_path / ".data" / PID / "marketing" / "field-pilots" / pid / "pilot.json"
    before = path.read_bytes()
    assert client.post(endpoint, files={"file": ("pos.csv", b"bad")}, data={"revision": "0"}).status_code == 400
    assert client.post(endpoint, files={"file": ("pos.csv", b"x" * (2 * 1024 * 1024 + 1))}, data={"revision": "0"}).status_code == 413
    assert client.post(endpoint, files={"file": ("pos.csv", b"bad")}, data={"revision": "-1"}).status_code == 422
    assert client.post(f"{ROOT}/staff-pilots/missing/pos/preview", files={"file": ("pos.csv", b"bad")}, data={"revision": "0"}).status_code == 404
    assert client.post("/api/projects/missing/staff-pilots/missing/pos/preview", files={"file": ("pos.csv", b"bad")}, data={"revision": "0"}).status_code == 404
    assert path.read_bytes() == before


def test_sensitivity_requires_closure_and_exports_a_readonly_revision(client, tmp_path):
    pid = create(client)["pilot"]["pilot_id"]
    endpoint = f"{ROOT}/staff-pilots/{pid}/sensitivity"
    assert client.get(endpoint, params={"revision": 0}).status_code == 409
    assert upload(client, pid, sheet(client, pid, complete=True)).status_code == 200
    assert client.get(endpoint, params={"revision": 1}).status_code == 409
    assert client.post(f"{ROOT}/staff-pilots/{pid}/close", json={"revision": 1}).status_code == 200
    path = tmp_path / ".data" / PID / "marketing" / "field-pilots" / pid / "pilot.json"
    before = path.read_bytes()
    response = client.get(endpoint, params={"revision": 2})
    assert response.status_code == 200, response.text
    assert response.json()["difference"] == 1 and response.json()["revision"] == 2
    assert response.json()["groups"][0]["difference"] is None
    exported = client.get(endpoint + ".csv", params={"revision": 2})
    assert exported.status_code == 200 and f"{pid}-sensitivity-r2.csv" in exported.headers["content-disposition"]
    assert len(list(csv.DictReader(io.StringIO(exported.text)))) == 3
    assert path.read_bytes() == before
    assert client.get(endpoint, params={"revision": 1}).status_code == 409
    assert client.get(endpoint + ".csv", params={"revision": 1}).status_code == 409
    assert client.delete(f"{ROOT}/staff-pitches/pit_test").status_code == 204
    assert client.get(endpoint, params={"revision": 2}).json() == response.json()


def test_sensitivity_rejects_early_closure_and_invalid_revision_or_scope(client):
    pid = create(client)["pilot"]["pilot_id"]
    rows = list(csv.DictReader(io.StringIO(sheet(client, pid).decode())))
    for row in rows:
        row["enrolled"] = "0"
    out = io.StringIO(); writer = csv.DictWriter(out, fieldnames=list(rows[0])); writer.writeheader(); writer.writerows(rows)
    assert upload(client, pid, out.getvalue().encode()).status_code == 200
    assert client.post(f"{ROOT}/staff-pilots/{pid}/close", json={"revision": 1}).status_code == 200
    endpoint = f"{ROOT}/staff-pilots/{pid}/sensitivity"
    assert client.get(endpoint, params={"revision": 2}).status_code == 409
    for suffix in ("", ".csv"):
        for query in ("", "?revision=-1", "?revision=1.5", "?revision=bad"):
            assert client.get(endpoint + suffix + query).status_code == 422
        assert client.get(endpoint.replace(pid, "missing") + suffix, params={"revision": 0}).status_code == 404
        assert client.get(endpoint.replace(PID, "missing") + suffix, params={"revision": 0}).status_code == 404


def test_sensitivity_rejects_corrupted_saved_assignments_without_touching_history(client, tmp_path):
    pid = create(client)["pilot"]["pilot_id"]
    assert upload(client, pid, sheet(client, pid, complete=True)).status_code == 200
    assert client.post(f"{ROOT}/staff-pilots/{pid}/close", json={"revision": 1}).status_code == 200
    path = tmp_path / ".data" / PID / "marketing" / "field-pilots" / pid / "pilot.json"
    data = read_json(path); data["assignments"] = []
    write_json(path, data); before = path.read_bytes()
    assert client.get(f"{ROOT}/staff-pilots/{pid}/sensitivity?revision=2").status_code == 409
    assert path.read_bytes() == before


def economics_request(**changes):
    return {"revision": 2, "currency": "KRW", "contribution_per_conversion_minor": 1000,
            "labor_per_hour_minor": 3600, "seconds_per_encounter_a": 0, "seconds_per_encounter_b": 60,
            "eligible_encounters_per_day": 100, **changes}


def test_cost_scenario_preview_and_csv_use_closed_revision_without_saving(client, tmp_path):
    pid = create(client)["pilot"]["pilot_id"]
    endpoint = f"{ROOT}/staff-pilots/{pid}/economics"
    assert client.post(endpoint, json=economics_request(revision=0)).status_code == 409
    assert upload(client, pid, sheet(client, pid, complete=True)).status_code == 200
    assert client.post(endpoint, json=economics_request(revision=1)).status_code == 409
    assert client.post(f"{ROOT}/staff-pilots/{pid}/close", json={"revision": 1}).status_code == 200
    root = tmp_path / ".data" / PID / "marketing" / "field-pilots" / pid
    before = {str(p.relative_to(root)): p.read_bytes() for p in root.rglob("*") if p.is_file()}
    response = client.post(endpoint, json=economics_request())
    assert response.status_code == 200, response.text
    data = response.json()
    assert data["per_encounter"]["estimate_minor"] == 940 and data["per_day"]["estimate_minor"] == 94000
    assert data["break_even_difference"] == 0.06
    exported = client.post(endpoint + ".csv", json=economics_request())
    assert exported.status_code == 200 and "cost-scenario-r2.csv" in exported.headers["content-disposition"]
    assert list(csv.DictReader(io.StringIO(exported.text)))[0]["per_day_estimate_minor"] == "94000.0"
    assert {str(p.relative_to(root)): p.read_bytes() for p in root.rglob("*") if p.is_file()} == before
    assert client.delete(f"{ROOT}/staff-pitches/pit_test").status_code == 204
    assert client.post(endpoint, json=economics_request()).json() == data


def test_cost_scenarios_reject_stale_invalid_and_unavailable_inputs(client, tmp_path):
    pid = create(client)["pilot"]["pilot_id"]
    assert upload(client, pid, sheet(client, pid, complete=True)).status_code == 200
    assert client.post(f"{ROOT}/staff-pilots/{pid}/close", json={"revision": 1}).status_code == 200
    endpoint = f"{ROOT}/staff-pilots/{pid}/economics"
    for suffix in ("", ".csv"):
        assert client.post(endpoint + suffix, json=economics_request(revision=1)).status_code == 409
        assert client.post(endpoint + suffix, json=economics_request(currency="USD")).status_code == 409
        for changes in ({"seconds_per_encounter_a": True}, {"contribution_per_conversion_minor": -1}, {"labor_per_hour_minor": "100"}):
            assert client.post(endpoint + suffix, json=economics_request(**changes)).status_code == 422
        assert client.post(endpoint + suffix, json={}).status_code == 422
        assert client.post(endpoint.replace(pid, "missing") + suffix, json=economics_request()).status_code == 404
        assert client.post(endpoint.replace(PID, "missing") + suffix, json=economics_request()).status_code == 404
    path = tmp_path / ".data" / PID / "marketing" / "field-pilots" / pid / "pilot.json"
    saved = read_json(path); saved["assignments"][0]["enrolled"] = False
    write_json(path, saved); before = path.read_bytes()
    assert client.post(endpoint, json=economics_request()).status_code == 409
    assert path.read_bytes() == before


def test_staff_timing_template_preview_and_export_are_read_only(client, tmp_path):
    pid = create(client)["pilot"]["pilot_id"]
    url = f"{ROOT}/staff-pilots/{pid}/timing"
    assert client.get(f"{url}/template.csv?revision=0").status_code == 409
    assert upload(client, pid, sheet(client, pid, complete=True)).status_code == 200
    assert client.post(f"{ROOT}/staff-pilots/{pid}/close", json={"revision": 1}).status_code == 200
    template = client.get(f"{url}/template.csv?revision=2")
    assert template.status_code == 200
    rows = list(csv.DictReader(io.StringIO(template.text)))
    assert len(rows) == 40 and all(r["staff_seconds"] == "" for r in rows)
    out = io.StringIO(); writer = csv.DictWriter(out, fieldnames=list(rows[0])); writer.writeheader()
    for row in rows: writer.writerow({**row, "staff_seconds": "0.001"})
    data = out.getvalue().encode()
    path = tmp_path / ".data" / PID / "marketing" / "field-pilots" / pid / "pilot.json"
    before = path.read_bytes()
    response = client.post(f"{url}/preview", files={"file": ("time.csv", data)}, data={"revision": "2"})
    assert response.status_code == 200, response.text
    assert response.json()["a"]["mean_seconds"] == 0.001 and response.json()["difference_seconds"] == 0
    audit = client.post(f"{url}/export.csv", files={"file": ("time.csv", data)}, data={"revision": "2"})
    assert audit.status_code == 200 and "staff-time-r2.csv" in audit.headers["content-disposition"]
    assert len(list(csv.DictReader(io.StringIO(audit.text)))) == 40
    assert client.post(f"{url}/preview", files={"file": ("time.csv", data)}, data={"revision": "1"}).status_code == 409
    assert path.read_bytes() == before


@pytest.mark.parametrize("suffix", ["preview", "export.csv"])
def test_timing_upload_errors_and_stale_exports_never_change_saved_pilot(client, tmp_path, suffix):
    pid = create(client)["pilot"]["pilot_id"]
    assert upload(client, pid, sheet(client, pid, complete=True)).status_code == 200
    assert client.post(f"{ROOT}/staff-pilots/{pid}/close", json={"revision": 1}).status_code == 200
    url = f"{ROOT}/staff-pilots/{pid}/timing/{suffix}"
    path = tmp_path / ".data" / PID / "marketing" / "field-pilots" / pid / "pilot.json"
    before = path.read_bytes()
    for revision, data, code in [("-1", b"bad", 422), ("1", b"bad", 409), ("2", b"bad", 400),
                                  ("2", b"x" * (2 * 1024 * 1024 + 1), 413)]:
        response = client.post(url, files={"file": ("time.csv", data)}, data={"revision": revision})
        assert response.status_code == code, response.text
    assert client.post(url.replace(pid, "missing"), files={"file": ("time.csv", b"bad")}, data={"revision": "2"}).status_code == 404
    assert path.read_bytes() == before
    saved = read_json(path); saved["pilot_id"] = "pilot_wrong"; write_json(path, saved)
    assert client.post(url, files={"file": ("time.csv", b"bad")}, data={"revision": "2"}).status_code == 409
