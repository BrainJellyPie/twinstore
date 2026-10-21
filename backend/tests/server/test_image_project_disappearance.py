"""Photo routes remain consistent when their project disappears."""
import io
import shutil

import pytest
from fastapi.testclient import TestClient
from PIL import Image

from store_emulator.application import projects
from store_emulator.application.storage import images
from store_emulator.application.storage.io import write_json


@pytest.fixture
def client(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    write_json(tmp_path / ".data" / "proj_test" / "metadata.json", {"currency": "USD"})
    from store_emulator.server.main import app
    return TestClient(app, raise_server_exceptions=False)


def photo_file():
    data = io.BytesIO()
    Image.new("RGB", (8, 8), "white").save(data, format="PNG")
    return {"file": ("tea.png", data.getvalue(), "image/png")}


@pytest.mark.parametrize("query_route", [False, True])
def test_orphaned_photos_are_not_served_without_their_project(client, tmp_path, query_route):
    uploaded = client.post("/api/projects/proj_test/sku-images", params={"sku": "tea"}, files=photo_file())
    assert uploaded.status_code == 200, uploaded.text
    # Older versions removed the project while leaving its photos elsewhere.
    shutil.rmtree(tmp_path / ".data" / "proj_test")
    assert (tmp_path / ".data" / "images" / "proj_test").exists()

    url = uploaded.json()["url"] if query_route else "/api/projects/proj_test/images/tea"
    response = client.get(url)

    assert response.status_code == 404, response.status_code


@pytest.mark.parametrize("query_route", [False, True])
def test_project_deleted_before_upload_response_returns_not_found(client, monkeypatch, query_route):
    save = images.save_image

    def save_then_delete(*args, **kwargs):
        entry = save(*args, **kwargs)
        projects.delete_project("proj_test")
        return entry

    monkeypatch.setattr(images, "save_image", save_then_delete)
    url = "/api/projects/proj_test/sku-images" if query_route else "/api/projects/proj_test/sku-images/tea"
    response = client.post(url, params={"sku": "tea"} if query_route else {}, files=photo_file())

    assert response.status_code == 404, response.text
    assert "no longer exists" in response.json()["detail"]
