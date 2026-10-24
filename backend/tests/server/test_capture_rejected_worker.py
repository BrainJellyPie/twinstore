"""A photo job rejected after queue insertion must never start later."""

import io
from concurrent.futures import ThreadPoolExecutor
from unittest.mock import Mock

import pytest
from fastapi.testclient import TestClient
from PIL import Image

from store_emulator.application import capture, projects
from store_emulator.application.storage.setups import metadata_path
from store_emulator.server.main import app
from tests.server.test_simulation_setup_races import PID, layout


@pytest.mark.parametrize("stable", [False, True])
@pytest.mark.parametrize("after_failure", ["keep", "delete_capture", "delete_project"])
def test_rejected_photo_does_not_resume_or_reappear(layout, monkeypatch, stable, after_failure):
    with Image.new("RGB", (160, 160), "blue") as photo:
        image = io.BytesIO()
        photo.save(image, format="PNG")
    analysis = Mock(side_effect=AssertionError("Rejected photos must not be analyzed"))
    monkeypatch.setattr(capture, "run_capture_sync", analysis)
    client = TestClient(app, raise_server_exceptions=False)
    form = {"detector": "classic", "model": "none"}
    if stable:
        form["request_id"] = "a" * 32
    with ThreadPoolExecutor(max_workers=1) as pool:
        monkeypatch.setattr(capture, "executor", pool)
        with monkeypatch.context() as failure:
            failure.setattr(pool, "_adjust_thread_count", Mock(side_effect=RuntimeError("can't start new thread")))
            response = client.post(f"/api/projects/{PID}/captures", data=form,
                files={"image": ("photo.png", image.getvalue(), "image/png")})
        assert response.status_code == 503, response.text
        records = capture.list_captures(PID)
        assert len(records) == 1 and records[0].status == "failed"
        cid = records[0].capture_id
        folder = metadata_path(PID).parent / "captures" / cid
        before = (folder / "status.json").read_bytes()
        if after_failure == "delete_capture":
            capture.delete_capture(PID, cid)
        elif after_failure == "delete_project":
            projects.delete_project(PID)
        pool.submit(lambda: None).result(timeout=5)
    analysis.assert_not_called()
    if after_failure == "keep":
        assert (folder / "status.json").read_bytes() == before
    else:
        assert not folder.exists()
        if after_failure == "delete_project":
            assert not metadata_path(PID).parent.exists()
