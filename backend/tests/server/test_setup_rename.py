"""Renaming a layout keeps a usable name."""
import pytest
from fastapi.testclient import TestClient

from store_emulator.application.storage.io import read_json, write_json
from store_emulator.application.storage.setups import new_setup_data


@pytest.fixture
def client(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    root = tmp_path / ".data" / "proj_test"
    write_json(root / "metadata.json", {"name": "Test", "currency": "USD"})
    setup = new_setup_data("Optimized", None, None)
    setup["id"] = "setup_a"
    write_json(root / "setups" / "setup_a.json", setup)
    from store_emulator.server.main import app
    return TestClient(app, raise_server_exceptions=False), root / "setups" / "setup_a.json"


def test_a_rename_is_trimmed(client):
    api, path = client
    response = api.put("/api/projects/proj_test/setups/setup_a", json={"setup": {"name": "  Wide aisles "}})
    assert response.status_code == 200, response.text
    assert read_json(path)["name"] == "Wide aisles"


@pytest.mark.parametrize("name", ["", "   ", "x" * 301])
def test_a_blank_or_overlong_name_is_refused_and_the_old_one_kept(client, name):
    api, path = client
    response = api.put("/api/projects/proj_test/setups/setup_a", json={"setup": {"name": name}})
    assert response.status_code == 422
    assert read_json(path)["name"] == "Optimized"
