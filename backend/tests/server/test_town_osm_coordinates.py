"""Bad map coordinates must fail before external work or replacing a saved town."""
from unittest.mock import Mock

import pytest
from fastapi.testclient import TestClient

from store_emulator.application import town
from store_emulator.application.storage.io import write_json


@pytest.fixture
def setup(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    write_json(tmp_path / ".data" / "proj_test" / "metadata.json", {"name": "Test"})
    from store_emulator.server.main import app
    client = TestClient(app)
    response = client.post("/api/projects/proj_test/town/generate", json={"seed": 17, "size_m": 200})
    assert response.status_code == 200
    fetch = Mock(return_value={"elements": []})
    geocode = Mock(return_value=(37.0, 127.0))
    monkeypatch.setattr(town, "fetch_overpass", fetch)
    monkeypatch.setattr(town, "geocode", geocode)
    return client, tmp_path / ".data" / "proj_test" / "town.json", fetch, geocode


@pytest.mark.parametrize("axis,value", [
    ("lat", 90.0001), ("lat", -90.0001), ("lon", 180.0001), ("lon", -180.0001),
    ("lat", "NaN"), ("lon", "NaN"), ("lat", "Infinity"), ("lon", "Infinity"),
    ("lat", "-Infinity"), ("lon", "-Infinity"),
])
@pytest.mark.parametrize("address", [None, "A valid fallback address"])
def test_invalid_coordinates_fail_before_fetch_or_geocoding_and_preserve_town(setup, axis, value, address):
    client, path, fetch, geocode = setup
    before = path.read_bytes()
    response = client.post("/api/projects/proj_test/town/import-osm", json={
        "lat": 37.0, "lon": 127.0, "radius_m": 150, "address": address, axis: value,
    })
    assert response.status_code == 422, response.text
    fetch.assert_not_called()
    geocode.assert_not_called()
    assert path.read_bytes() == before
    assert client.get("/api/projects/proj_test/town/demand").status_code == 200


@pytest.mark.parametrize("lat,lon", [(0, 0), (-90, -180), (-90, 180), (90, -180), (90, 180), (37.5, 127.5)])
def test_boundary_coordinates_remain_valid_without_geocoding(setup, lat, lon):
    client, _, fetch, geocode = setup
    response = client.post("/api/projects/proj_test/town/import-osm", json={"lat": lat, "lon": lon, "radius_m": 150})
    assert response.status_code == 200, response.text
    assert (response.json()["center_lat"], response.json()["center_lon"]) == (lat, lon)
    fetch.assert_called_once_with(lat, lon, 150)
    geocode.assert_not_called()


def test_address_only_import_keeps_coordinate_fallback(setup):
    client, _, fetch, geocode = setup
    response = client.post("/api/projects/proj_test/town/import-osm", json={"address": "Test address", "radius_m": 150})
    assert response.status_code == 200, response.text
    geocode.assert_called_once_with("Test address")
    fetch.assert_called_once_with(37.0, 127.0, 150)


@pytest.mark.parametrize("field,value", [("center_lat", 90.0001), ("center_lat", -90.0001), ("center_lon", 180.0001), ("center_lon", -180.0001)])
def test_invalid_saved_coordinates_cannot_overwrite_the_existing_town(setup, field, value):
    client, path, fetch, geocode = setup
    before = path.read_bytes()
    existing = client.get("/api/projects/proj_test/town").json()
    existing[field] = value
    response = client.put("/api/projects/proj_test/town", json=existing)
    assert response.status_code == 422, response.text
    assert path.read_bytes() == before
    fetch.assert_not_called()
    geocode.assert_not_called()


@pytest.mark.parametrize("axis", ["lat", "lon"])
@pytest.mark.parametrize("literal", ["NaN", "Infinity", "-Infinity"])
def test_nonfinite_json_numbers_return_a_serializable_validation_error(setup, axis, literal):
    client, path, fetch, geocode = setup
    before = path.read_bytes()
    other = '"lon":127' if axis == "lat" else '"lat":37'
    response = client.post("/api/projects/proj_test/town/import-osm",
        content=f'{{"{axis}":{literal},{other},"radius_m":150}}', headers={"content-type": "application/json"})
    assert response.status_code == 422, response.text
    assert isinstance(response.json()["detail"], list)
    fetch.assert_not_called()
    geocode.assert_not_called()
    assert path.read_bytes() == before
