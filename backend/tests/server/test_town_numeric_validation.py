"""Invalid neighborhood measurements must not replace a working demand model."""

import pytest
from fastapi.testclient import TestClient

from store_emulator.application.storage.io import write_json


@pytest.fixture
def client(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    write_json(tmp_path / ".data" / "proj_test" / "metadata.json", {"name": "Test"})
    from store_emulator.server.main import app
    return TestClient(app)


@pytest.mark.parametrize("section,field,value", [
    ("venues", "attractiveness", "Infinity"),
    ("venues", "x", "NaN"),
    ("buildings", "width", "Infinity"),
    ("buildings", "y", "-Infinity"),
    (None, "size_m", "NaN"),
    (None, "center_lat", "Infinity"),
])
def test_nonfinite_town_edit_is_rejected_without_replacing_saved_data(client, tmp_path, section, field, value):
    url = "/api/projects/proj_test/town"
    response = client.post(f"{url}/generate", json={"seed": 1, "size_m": 200, "density": 0.2})
    assert response.status_code == 200
    town = response.json()
    path = tmp_path / ".data" / "proj_test" / "town.json"
    before = path.read_bytes()
    target = town[section][0] if section else town
    target[field] = value

    response = client.put(url, json=town)

    assert response.status_code == 422
    assert path.read_bytes() == before


def test_nonfinite_new_venue_is_rejected_before_saving(client, tmp_path):
    url = "/api/projects/proj_test/town"
    assert client.post(f"{url}/generate", json={"seed": 1, "size_m": 200}).status_code == 200
    path = tmp_path / ".data" / "proj_test" / "town.json"
    before = path.read_bytes()

    response = client.post(f"{url}/venues", json={"category": "cafe", "x": "NaN", "y": 100})

    assert response.status_code == 422
    assert path.read_bytes() == before
