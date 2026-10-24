"""A rejected photo upload must not leave an unqueued pending capture or consume its retry ID."""

import io
from pathlib import Path
from unittest.mock import Mock

import pytest
from fastapi.testclient import TestClient
from PIL import Image

from store_emulator.application import capture
from store_emulator.application.storage.setups import metadata_path
from store_emulator.server.main import app
from tests.server.test_simulation_setup_races import PID, layout


@pytest.mark.parametrize("stable, stage", [(True, "receipt"), (True, "image"), (True, "status"),
                                         (False, "image"), (False, "status")])
@pytest.mark.parametrize("after_write", [False, True])
def test_rejected_upload_rolls_back_persistence_and_allows_retry(layout, monkeypatch, stable, stage, after_write):
    with Image.new("RGB", (160, 160), "blue") as photo:
        data = io.BytesIO()
        photo.save(data, format="PNG")
    submit = Mock()
    monkeypatch.setattr(capture.executor, "submit", submit)
    client = TestClient(app, raise_server_exceptions=False)
    form = {"detector": "classic", "model": "none"}
    if stable:
        form["request_id"] = "a" * 32

    def post():
        return client.post(f"/api/projects/{PID}/captures", data=form,
                           files={"image": ("사진.png", data.getvalue(), "image/png")})

    with monkeypatch.context() as failure:
        if stage == "image":
            original_save = Image.Image.save

            def save(self, path, *args, **kwargs):
                if Path(path).name == "image.jpg":
                    if after_write:
                        original_save(self, path, *args, **kwargs)
                    raise OSError("offline image persistence failure")
                return original_save(self, path, *args, **kwargs)

            failure.setattr(Image.Image, "save", save)
        else:
            original_write = capture.write_json

            def write(path, payload):
                if (stage == "receipt" and path.parent.name == ".uploads") or (stage == "status" and path.name == "status.json"):
                    if after_write:
                        original_write(path, payload)
                    raise OSError("offline capture persistence failure")
                return original_write(path, payload)

            failure.setattr(capture, "write_json", write)
        response = post()
    assert response.status_code == 500, response.text
    submit.assert_not_called()
    base = metadata_path(PID).parent / "captures"
    assert capture.list_captures(PID) == []
    assert not any(p.is_dir() and p.name != ".uploads" for p in base.iterdir())
    assert not list((base / ".uploads").glob("*.json"))
    retried = post()
    assert retried.status_code == 200, retried.text
    submit.assert_called_once()
    assert len(capture.list_captures(PID)) == 1
