"""Creating a layout requires an existing project, including when no source is copied."""

import pytest
from fastapi.testclient import TestClient

from store_emulator.application.storage.io import write_json


@pytest.fixture
def client(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    from store_emulator.server.main import app
    return TestClient(app)


def test_empty_layout_cannot_create_an_orphan_project(client, tmp_path):
    response = client.post("/api/projects/proj_missing/setups", json={"mode": "empty"})
    assert response.status_code == 404
    assert not (tmp_path / ".data" / "proj_missing").exists()


def test_empty_layout_can_be_added_to_an_existing_project(client, tmp_path):
    write_json(tmp_path / ".data" / "proj_test" / "metadata.json", {"name": "Test"})
    response = client.post("/api/projects/proj_test/setups", json={"mode": "empty", "name": "Empty layout"})
    assert response.status_code == 200
    layout = response.json()
    assert layout["name"] == "Empty layout" and layout["parentId"] is None
    assert (tmp_path / ".data" / "proj_test" / "setups" / f"{layout['id']}.json").exists()
