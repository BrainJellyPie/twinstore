"""Product image commits and locks must not recreate a project after deletion."""

import io

import pytest
from fastapi.testclient import TestClient
from PIL import Image

from store_emulator.application import projects, shelf_lab
from store_emulator.application.storage.setups import metadata_path
from store_emulator.server.main import app
from tests.server.test_package_read_conflicts import pack, reader
from tests.server.test_shelf_lab_start_snapshot import overlap


@pytest.fixture
def package_client(pack, monkeypatch):
    pid, aid, _ = pack
    reader(monkeypatch)
    image = io.BytesIO()
    Image.new("RGB", (12, 16), "blue").save(image, format="PNG")
    return TestClient(app, raise_server_exceptions=False), pid, aid, image.getvalue()


def action(client, pid, aid, data, operation):
    url = f"/api/projects/{pid}/lab/packages"
    if operation == "upload":
        return client.post(url, files={"image": ("new.png", data, "image/png")}, data={"remove_background": "false"})
    if operation == "update":
        return client.patch(f"{url}/{aid}", json={"name": "Updated"})
    if operation == "read":
        return client.post(f"{url}/{aid}/read", json={})
    return client.delete(f"{url}/{aid}")


@pytest.mark.parametrize("operation", ["upload", "update", "read", "delete"])
def test_deletion_accepted_first_prevents_late_package_operations(package_client, monkeypatch, operation):
    client, pid, aid, data = package_client
    removed, result = overlap(monkeypatch, projects, "remove_tree", lambda: client.delete(f"/api/projects/{pid}"),
                              lambda: action(client, pid, aid, data, operation))
    assert removed.status_code == 200, removed.text
    assert result.status_code == 404, result.text
    assert not metadata_path(pid).parent.exists()


@pytest.mark.parametrize("operation", ["upload", "update", "read"])
def test_package_commit_finishes_before_waiting_project_deletion(package_client, monkeypatch, operation):
    client, pid, aid, data = package_client
    result, removed = overlap(monkeypatch, shelf_lab, "write_json",
                              lambda: action(client, pid, aid, data, operation),
                              lambda: client.delete(f"/api/projects/{pid}"))
    assert result.status_code == 200, result.text
    assert removed.status_code == 200, removed.text
    assert not metadata_path(pid).parent.exists()


@pytest.mark.parametrize("operation", ["update", "read", "delete"])
def test_package_lock_creation_cannot_outlive_project_deletion(package_client, monkeypatch, operation):
    client, pid, aid, data = package_client
    result, removed = overlap(monkeypatch, shelf_lab, "FileLock",
                              lambda: action(client, pid, aid, data, operation),
                              lambda: client.delete(f"/api/projects/{pid}"))
    expected = (200, 404) if operation == "read" else (204,) if operation == "delete" else (200,)
    assert result.status_code in expected, result.text
    assert removed.status_code == 200, removed.text
    assert not metadata_path(pid).parent.exists()


def test_project_deleted_during_image_preparation_is_not_recreated(package_client, monkeypatch):
    client, pid, aid, data = package_client
    thumbnail = Image.Image.thumbnail

    def removed_during_resize(self, *args, **kwargs):
        result = thumbnail(self, *args, **kwargs)
        removed = client.delete(f"/api/projects/{pid}")
        assert removed.status_code == 200, removed.text
        return result

    monkeypatch.setattr(Image.Image, "thumbnail", removed_during_resize)
    result = action(client, pid, aid, data, "upload")
    assert result.status_code == 404, result.text
    assert not metadata_path(pid).parent.exists()


def test_project_deleted_while_model_answers_stays_deleted(package_client, monkeypatch):
    client, pid, aid, data = package_client

    def remove():
        result = client.delete(f"/api/projects/{pid}")
        assert result.status_code == 200, result.text

    reader(monkeypatch, action=remove)
    result = action(client, pid, aid, data, "read")
    assert result.status_code == 404, result.text
    assert not metadata_path(pid).parent.exists()


def test_corrupt_saved_image_fails_before_a_model_call(package_client, monkeypatch):
    client, pid, aid, data = package_client
    png = shelf_lab.package_path(pid, aid)
    png.write_bytes(b"not an image")
    before = png.with_suffix(".json").read_bytes()

    def unexpected_model():
        pytest.fail("An unreadable stored image must not call a provider")

    reader(monkeypatch, action=unexpected_model)
    result = action(client, pid, aid, data, "read")
    assert result.status_code == 400, result.text
    assert png.read_bytes() == b"not an image"
    assert png.with_suffix(".json").read_bytes() == before
