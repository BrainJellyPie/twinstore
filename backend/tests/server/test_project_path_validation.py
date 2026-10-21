"""Project path parameters must never resolve to the data directory or its parent."""

from unittest.mock import Mock

import pytest
from fastapi.testclient import TestClient

from store_emulator.application import projects, setups


@pytest.fixture
def client(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    from store_emulator.server.main import app
    return TestClient(app)


@pytest.mark.parametrize("project_id", ["%2e", "%2e%2e", "..%5coutside", "C%3Aoutside", "%00"])
def test_unsafe_project_ids_never_reach_delete(client, monkeypatch, project_id):
    delete = Mock()
    monkeypatch.setattr(projects, "delete_project", delete)
    response = client.delete(f"/api/projects/{project_id}")
    assert response.status_code == 400
    delete.assert_not_called()


def test_project_validation_applies_to_reads_writes_and_nested_routes(client, monkeypatch):
    read, write, nested = Mock(return_value={}), Mock(), Mock(return_value=[])
    monkeypatch.setattr(projects, "load_project", read)
    monkeypatch.setattr(projects, "update_project_metadata", write)
    monkeypatch.setattr(setups, "get_setups", nested)
    assert client.get("/api/projects/%2e%2e").status_code == 400
    assert client.put("/api/projects/%2e%2e/metadata", json={"name": "Test"}).status_code == 400
    assert client.get("/api/projects/%2e%2e/setups").status_code == 400
    read.assert_not_called()
    write.assert_not_called()
    nested.assert_not_called()


def test_valid_ids_and_routes_without_project_ids_still_work(client, monkeypatch):
    delete = Mock()
    monkeypatch.setattr(projects, "delete_project", delete)
    assert client.delete("/api/projects/proj_Test-123").status_code == 200
    delete.assert_called_once_with("proj_Test-123")
    assert client.get("/api/projects").status_code == 200
    assert client.get("/api/health").status_code == 200
