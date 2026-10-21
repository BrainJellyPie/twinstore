"""Saving personas requires a project, not just an existing directory."""
import json

import pytest
from fastapi.testclient import TestClient

from store_emulator.application.storage.io import write_json


@pytest.mark.parametrize("pid", ["proj_incomplete", "images"])
def test_personas_cannot_be_saved_into_non_project_directories(tmp_path, monkeypatch, pid):
    monkeypatch.chdir(tmp_path)
    root = tmp_path / ".data" / pid
    root.mkdir(parents=True)
    before = set(tmp_path.rglob("*"))
    from store_emulator.server.main import app
    response = TestClient(app, raise_server_exceptions=False).put(f"/api/projects/{pid}/personas", json={"personas": []})
    assert response.status_code == 404, response.text
    assert set(tmp_path.rglob("*")) == before


def test_personas_can_be_cleared_in_a_real_unlocked_project(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    root = tmp_path / ".data" / "proj_test"
    write_json(root / "metadata.json", {"name": "Test", "currency": "USD"})
    write_json(root / "personas.json", [{"id": "old"}])
    from store_emulator.server.main import app
    response = TestClient(app).put("/api/projects/proj_test/personas", json={"personas": []})
    assert response.status_code == 200, response.text
    assert json.loads((root / "personas.json").read_text()) == []
