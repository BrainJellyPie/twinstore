"""A failed status commit must release job guards before any expensive work starts."""

import io
from unittest.mock import Mock

import pytest
from fastapi.testclient import TestClient
from PIL import Image

from store_emulator.application import capture, optimize, projects, shelf_lab, town_synergy
from store_emulator.application.storage import io as storage_io
from store_emulator.application.storage.io import read_json
from store_emulator.application.storage.setups import metadata_path
from store_emulator.domain.capture import CaptureResult
from store_emulator.domain.optimize import OptimizeResult
from store_emulator.domain.town import VLMSynergyResult
from store_emulator.server.main import app
from tests.server.test_shelf_lab_start_snapshot import CID, lab
from tests.server.test_simulation_setup_races import PID, layout
from tests.server.test_study_queue_failure import studies


@pytest.fixture
def fail_status_commit(monkeypatch, request):
    target = getattr(request, "param", "running")
    original = storage_io.replace_file
    failures = []

    def replace(source, destination):
        if destination.name == "status.json" and read_json(source).get("status") == target and not failures:
            failures.append(destination)
            raise OSError("Offline transient status replace failure")
        return original(source, destination)

    monkeypatch.setattr(storage_io, "replace_file", replace)
    return failures


def assert_failed_and_deletable(failures):
    assert len(failures) == 1
    status = read_json(failures[0])
    assert status["status"] == "failed", status
    assert status["finished_at"] and status["error"]
    root = metadata_path(PID).parent
    projects.delete_project(PID)
    assert not root.exists()


@pytest.mark.parametrize("kind", ["optimization", "synergy", "experiment", "survey", "shelf", "conjoint", "pitch"])
def test_study_start_status_failure_is_terminal(studies, monkeypatch, fail_status_commit, kind):
    client, requests = studies
    module, endpoint, body = requests[kind]
    pool = Mock()
    monkeypatch.setattr(module, "executor", pool)
    response = client.post(f"/api/projects/{PID}/{endpoint}", json=body)
    assert response.status_code == 200, response.text
    args = pool.submit.call_args.args
    args[0](*args[1:])
    assert_failed_and_deletable(fail_status_commit)


@pytest.mark.parametrize("kind", ["audit", "sim2real"])
def test_shelf_lab_start_status_failure_is_terminal(lab, monkeypatch, fail_status_commit, kind):
    client, submit, body, _ = lab
    response = client.post(f"/api/projects/{PID}/captures/{CID}/{kind}", json=body if kind == "audit" else {})
    assert response.status_code == 200, response.text
    args = submit.call_args.args
    args[0](*args[1:])
    assert_failed_and_deletable(fail_status_commit)


@pytest.mark.parametrize("fail_status_commit", ["running", "completed"], indirect=True)
def test_capture_status_failure_does_not_hold_project(layout, monkeypatch, fail_status_commit):
    pool = Mock()
    analysis = Mock(return_value=CaptureResult(image_size=(160, 160)))
    monkeypatch.setattr(capture, "executor", pool)
    monkeypatch.setattr(capture, "run_capture_sync", analysis)
    with Image.new("RGB", (160, 160), "blue") as photo:
        image = io.BytesIO()
        photo.save(image, format="PNG")
    response = TestClient(app).post(f"/api/projects/{PID}/captures", data={"detector": "classic", "model": "none"},
        files={"image": ("photo.png", image.getvalue(), "image/png")})
    assert response.status_code == 200, response.text
    args = pool.submit.call_args.args
    args[0](*args[1:])
    assert analysis.call_count == int((fail_status_commit[0].parent / "result.json").exists())
    assert_failed_and_deletable(fail_status_commit)


@pytest.mark.parametrize("kind", ["optimization", "synergy"])
@pytest.mark.parametrize("fail_status_commit", ["completed"], indirect=True)
def test_study_completion_status_failure_is_terminal(studies, monkeypatch, fail_status_commit, kind):
    client, requests = studies
    module, endpoint, body = requests[kind]
    pool = Mock()
    monkeypatch.setattr(module, "executor", pool)
    calls = []

    async def search(store, spec, *args, **kwargs):
        calls.append("search")
        return OptimizeResult(spec=spec, baseline_score=100, best_score=110, relative_improvement=.1,
            best_store=store, applied_moves=[], history=[], evaluations=1, seconds=0)

    async def synergy(*args, **kwargs):
        calls.append("synergy")
        return VLMSynergyResult(venue_id="cafe", venue_name="Cafe", category="cafe", distance_m=10,
            day_type="weekday", visitors_with=20, visitors_without=20, delta_visitors=0,
            linked_visitors_from_venue=0, panel_customers=20, affected_customers=20, affected_share=1,
            spend_per_visitor_with=100, spend_per_visitor_without=100, delta_spend_per_visitor=0,
            conversion_with=1, conversion_without=1, delta_conversion=0, revenue_per_day_with=2000,
            revenue_per_day_without=2000, delta_revenue_per_day=0, delta_revenue_from_visitors=0,
            delta_revenue_from_baskets=0)

    monkeypatch.setattr(optimize, "optimize", search)
    monkeypatch.setattr(town_synergy, "vlm_basket_synergy", synergy)
    monkeypatch.setattr(town_synergy, "build_client", Mock())
    monkeypatch.setattr(town_synergy, "build_engine", Mock())
    response = client.post(f"/api/projects/{PID}/{endpoint}", json=body)
    assert response.status_code == 200, response.text
    args = pool.submit.call_args.args
    args[0](*args[1:])
    assert len(calls) == 1
    assert (fail_status_commit[0].parent / "result.json").is_file()
    assert_failed_and_deletable(fail_status_commit)


@pytest.mark.parametrize("fail_status_commit", ["canceled"], indirect=True)
def test_failed_cancellation_commit_releases_optimization(studies, monkeypatch, fail_status_commit):
    client, requests = studies
    module, endpoint, body = requests["optimization"]
    pool = Mock()
    monkeypatch.setattr(module, "executor", pool)
    work = Mock(side_effect=AssertionError("Canceled work cannot start"))
    monkeypatch.setattr(optimize, "optimize", work)
    response = client.post(f"/api/projects/{PID}/{endpoint}", json=body)
    assert response.status_code == 200, response.text
    job = response.json()["job_id"]
    optimize.cancel_optimization(PID, job)
    args = pool.submit.call_args.args
    args[0](*args[1:])
    assert (PID, job) not in optimize._cancel_requests
    work.assert_not_called()
    assert_failed_and_deletable(fail_status_commit)
