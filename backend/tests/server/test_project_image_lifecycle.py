"""Project image ownership persists across uploads and project deletion."""
import io

import pytest
from fastapi.testclient import TestClient
from PIL import Image

from store_emulator.application.storage.io import write_json


@pytest.fixture
def client(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    from store_emulator.server.main import app
    return TestClient(app, raise_server_exceptions=False)


def upload(client, pid):
    out = io.BytesIO()
    Image.new("RGB", (8, 8), "white").save(out, format="PNG")
    return client.post(f"/api/projects/{pid}/sku-images/tea", files={"file": ("tea.png", out.getvalue(), "image/png")})


def create_project(tmp_path, pid):
    write_json(tmp_path / ".data" / pid / "metadata.json", {"currency": "USD"})


def test_nonexistent_project_cannot_store_images(client, tmp_path):
    response = upload(client, "proj_missing")
    assert response.status_code == 404, response.text
    assert not (tmp_path / ".data").exists()


def test_shared_image_directory_cannot_be_deleted_as_a_project(client, tmp_path):
    create_project(tmp_path, "proj_test")
    uploaded = upload(client, "proj_test")
    assert uploaded.status_code == 200, uploaded.text
    response = client.delete("/api/projects/images")
    assert response.status_code == 404, response.text
    assert client.get(uploaded.json()["url"]).status_code == 200


def test_deleting_project_removes_only_its_images(client, tmp_path):
    uploads = {}
    for pid in ("proj_test", "proj_other"):
        create_project(tmp_path, pid)
        uploads[pid] = upload(client, pid)
        assert uploads[pid].status_code == 200
    response = client.delete("/api/projects/proj_test")
    assert response.status_code == 200, response.text
    assert client.get(uploads["proj_test"].json()["url"]).status_code == 404
    assert not (tmp_path / ".data" / "images" / "proj_test").exists()
    assert client.get(uploads["proj_other"].json()["url"]).status_code == 200


@pytest.mark.parametrize("state", ["pending", "running"])
def test_active_project_keeps_its_images(client, tmp_path, state):
    create_project(tmp_path, "proj_test")
    uploaded = upload(client, "proj_test")
    assert uploaded.status_code == 200
    write_json(tmp_path / ".data" / "proj_test" / "runs" / "run_test" / "status.json", {"status": state})
    response = client.delete("/api/projects/proj_test")
    assert response.status_code == 409, response.text
    assert client.get(uploaded.json()["url"]).status_code == 200


def test_deletion_cleans_up_an_upload_already_in_progress(client, tmp_path, monkeypatch):
    from concurrent.futures import ThreadPoolExecutor
    from pathlib import Path
    from threading import Event

    from store_emulator.application import projects
    from store_emulator.application.storage import images
    from store_emulator.engine import files

    create_project(tmp_path, "proj_test")
    data = io.BytesIO()
    Image.new("RGB", (8, 8), "white").save(data, format="PNG")
    upload_ready, allow_upload, project_removed = Event(), Event(), Event()
    original_replace = Path.replace
    original_rmtree = files.shutil.rmtree

    def pause_upload(path, target):
        if Path(target).suffix == ".png":
            upload_ready.set()
            assert allow_upload.wait(10)
        return original_replace(path, target)

    def track_project_removal(path, *args, **kwargs):
        result = original_rmtree(path, *args, **kwargs)
        if Path(path) == Path(".data/proj_test"):
            project_removed.set()
        return result

    monkeypatch.setattr(Path, "replace", pause_upload)
    monkeypatch.setattr(files.shutil, "rmtree", track_project_removal)
    with ThreadPoolExecutor(max_workers=2) as pool:
        saving = pool.submit(images.save_image, "proj_test", "tea", data.getvalue(), "tea.png")
        try:
            assert upload_ready.wait(10)
            deleting = pool.submit(projects.delete_project, "proj_test")
            assert project_removed.wait(10)
        finally:
            allow_upload.set()
        saving.result(timeout=10)
        deleting.result(timeout=10)

    assert not (tmp_path / ".data" / "images" / "proj_test").exists()
