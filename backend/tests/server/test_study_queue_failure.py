"""Rejected optimization and research jobs must release deletion and retry guards."""

import io
from concurrent.futures import ThreadPoolExecutor
from unittest.mock import Mock

import pytest
from fastapi.testclient import TestClient
from PIL import Image

from store_emulator.application import capture, marketing, optimize, projects, shelf_lab, staff_pitch, town_synergy
from store_emulator.application.storage.io import read_json, write_json
from store_emulator.application.storage.setups import metadata_path, personas_path, read_setup
from store_emulator.domain.config import LLMConfig
from store_emulator.domain.town import Town, TownArchetype, Venue, VenueCategory
from store_emulator.server.main import app
from tests.server.test_shelf_lab_start_snapshot import CID, lab
from tests.server.test_simulation_setup_races import PID, SID, layout


@pytest.fixture
def studies(layout, monkeypatch):
    person = read_json(personas_path(PID))[0]
    write_json(personas_path(PID), [{**person, "id": f"person_{i}"} for i in range(20)])
    monkeypatch.setattr(marketing, "capture_llm_config", lambda *a, **k: LLMConfig(model="offline"))
    monkeypatch.setattr(marketing, "LiteLLMClient", Mock(side_effect=AssertionError("Rejected jobs cannot call models")))
    monkeypatch.setattr(staff_pitch, "build_client", Mock())
    monkeypatch.setattr(town_synergy, "ensure_resolvable", lambda *a: None)
    monkeypatch.setattr(town_synergy, "with_vision_default", lambda config, model: config)
    store = read_setup(PID, SID)["store"]
    rack = next(r for r in store["racks"] if r["slots"])
    sku = rack["slots"][0]["items"][0]["sku"]
    town = Town(id="town", name="Town", archetype=TownArchetype.RESIDENTIAL, size_m=200,
        focal_venue_id="store", venues=[
            Venue(id="store", name="Store", category=VenueCategory.CONVENIENCE, x=100, y=100, setup_id=SID),
            Venue(id="cafe", name="Cafe", category=VenueCategory.CAFE, x=110, y=100)])
    write_json(metadata_path(PID).parent / "town.json", town.model_dump(mode="json"))
    with Image.new("RGB", (160, 160), "blue") as photo:
        image = io.BytesIO()
        photo.save(image, format="PNG")
    asset = shelf_lab.upload_package(PID, image.getvalue(), "Test.png", remove_background=False)
    change = {"kind": "promo", "sku": sku, "promo": "NEW"}
    requests = {
        "optimization": (optimize, f"setups/{SID}/optimize", {}),
        "synergy": (town_synergy, "town/venues/cafe/synergy-vlm", {"setup_id": SID}),
        "experiment": (marketing, "experiments", {"setup_id": SID, "engine": "rule", "panel": 20,
            "variants": [{"name": "Sign", "changes": [change]}]}),
        "survey": (marketing, "surveys", {"stimuli": [asset.asset_id], "questions": ["value"], "currency": "USD"}),
        "shelf": (marketing, "shelf-tests", {"setup_id": SID, "rack_id": rack["id"], "target_sku": sku,
            "panel": 10, "changes": [change]}),
        "conjoint": (marketing, "conjoints", {"product": "Tea", "attributes": [{"name": "Style", "levels": ["A", "B"]}],
            "prices": [100, 200], "currency": "USD", "panel": 10}),
        "pitch": (staff_pitch, "staff-pitches", {"setup_id": SID, "sku": sku, "panel": 20, "context": "At the shelf",
            "variants": [{"name": "A", "script": "Hello"}, {"name": "B", "script": "Welcome"}]}),
    }
    return TestClient(app, raise_server_exceptions=False), requests


@pytest.mark.parametrize("kind", ["optimization", "synergy", "experiment", "survey", "shelf", "conjoint", "pitch"])
@pytest.mark.parametrize("queued", [False, True])
def test_rejected_study_is_failed_retryable_and_cannot_recreate_a_deleted_project(studies, monkeypatch, kind, queued):
    client, requests = studies
    module, endpoint, body = requests[kind]
    root = metadata_path(PID).parent
    with ThreadPoolExecutor(max_workers=1) as pool:
        monkeypatch.setattr(module, "executor", pool)
        with monkeypatch.context() as failure:
            method = "_adjust_thread_count" if queued else "submit"
            failure.setattr(pool, method, Mock(side_effect=RuntimeError("offline executor start failure")))
            response = client.post(f"/api/projects/{PID}/{endpoint}", json=body)
        records = list(root.rglob("status.json"))
        assert len(records) == 1
        status = read_json(records[0])
        assert status["status"] == "failed", status
        assert response.status_code == 503, response.text
        assert status["finished_at"] and "could not start" in status["error"].lower()
        if queued:
            projects.delete_project(PID)
            pool.submit(lambda: None).result(timeout=5)
            assert not root.exists()
        else:
            accepted = Mock()
            monkeypatch.setattr(pool, "submit", accepted)
            retry = client.post(f"/api/projects/{PID}/{endpoint}", json=body)
            assert retry.status_code == 200, retry.text
            accepted.assert_called_once()
            assert sorted(read_json(path)["status"] for path in root.rglob("status.json")) == ["failed", "pending"]


@pytest.mark.parametrize("kind", ["audit", "sim2real"])
@pytest.mark.parametrize("queued", [False, True])
def test_rejected_shelf_lab_job_is_retryable_and_cannot_restore_a_deleted_photo(lab, monkeypatch, kind, queued):
    _, _, body, root = lab
    client = TestClient(app, raise_server_exceptions=False)
    url = f"/api/projects/{PID}/captures/{CID}/{kind}"
    payload = body if kind == "audit" else {}
    with ThreadPoolExecutor(max_workers=1) as pool:
        monkeypatch.setattr(shelf_lab, "executor", pool)
        with monkeypatch.context() as failure:
            failure.setattr(pool, "_adjust_thread_count" if queued else "submit",
                            Mock(side_effect=RuntimeError("offline executor start failure")))
            response = client.post(url, json=payload)
        jobs = shelf_lab.list_jobs(PID, CID)
        assert len(jobs) == 1 and jobs[0].status == "failed"
        assert response.status_code == 503, response.text
        assert jobs[0].finished_at and "could not start" in jobs[0].error.lower()
        if queued:
            capture.delete_capture(PID, CID)
            pool.submit(lambda: None).result(timeout=5)
            assert not root.exists()
        else:
            accepted = Mock()
            monkeypatch.setattr(pool, "submit", accepted)
            retry = client.post(url, json=payload)
            assert retry.status_code == 200, retry.text
            accepted.assert_called_once()
            assert sorted(job.status for job in shelf_lab.list_jobs(PID, CID)) == ["failed", "pending"]
