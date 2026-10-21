"""Reject structurally broken neighborhood replacements before overwriting saved data."""

from copy import deepcopy

import pytest
from fastapi.testclient import TestClient

from store_emulator.application.storage.io import write_json


@pytest.fixture
def client(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    write_json(tmp_path / ".data" / "proj_test" / "metadata.json", {"name": "Test"})
    from store_emulator.server.main import app
    return TestClient(app)


@pytest.fixture
def saved(client):
    response = client.post("/api/projects/proj_test/town/generate", json={"seed": 17, "size_m": 200, "n_competitors": 1})
    assert response.status_code == 200
    return response.json()


@pytest.mark.parametrize("case", ["missing_reference", "removed_focal", "empty_reference", "zero_size", "negative_size"])
def test_invalid_town_structure_preserves_saved_town_and_working_demand(client, saved, tmp_path, case):
    url = "/api/projects/proj_test/town"
    path = tmp_path / ".data" / "proj_test" / "town.json"
    before = path.read_bytes()
    demand = client.get(f"{url}/demand").json()
    if case == "missing_reference":
        saved["focal_venue_id"] = "missing"
    elif case == "empty_reference":
        saved["focal_venue_id"] = ""
    elif case == "removed_focal":
        saved["venues"] = [v for v in saved["venues"] if v["id"] != saved["focal_venue_id"]]
    else:
        saved["size_m"] = 0 if case == "zero_size" else -1

    response = client.put(url, json=saved)

    assert response.status_code == 422, response.text
    assert path.read_bytes() == before
    current = client.get(f"{url}/demand")
    assert current.status_code == 200 and current.json() == demand


@pytest.mark.parametrize("section", ["venues", "buildings", "roads"])
@pytest.mark.parametrize("invalid", ["duplicate", "empty", "blank"])
def test_ambiguous_ids_cannot_replace_saved_town(client, saved, tmp_path, section, invalid):
    path = tmp_path / ".data" / "proj_test" / "town.json"
    before = path.read_bytes()
    assert saved[section]
    if invalid == "duplicate":
        saved[section].append(deepcopy(saved[section][0]))
    else:
        saved[section][0]["id"] = "" if invalid == "empty" else " \t "

    response = client.put("/api/projects/proj_test/town", json=saved)

    assert response.status_code == 422, response.text
    assert path.read_bytes() == before


def test_valid_edit_keeps_ids_scoped_to_each_section_and_small_positive_maps(client, saved):
    # OSM-style external IDs need not match project resource IDs. A building and
    # its venue can intentionally carry the same external reference.
    original_focal = saved["focal_venue_id"]
    saved["focal_venue_id"] = "node/123:store"
    next(v for v in saved["venues"] if v["id"] == original_focal)["id"] = saved["focal_venue_id"]
    saved["buildings"][0]["id"] = saved["focal_venue_id"]
    saved["roads"][0]["id"] = saved["focal_venue_id"]
    saved["size_m"] = 150
    response = client.put("/api/projects/proj_test/town", json=saved)
    assert response.status_code == 200, response.text
    assert client.get("/api/projects/proj_test/town").json() == saved
    assert client.get("/api/projects/proj_test/town/demand").status_code == 200


def test_invalid_first_save_does_not_create_a_town(client, tmp_path):
    response = client.put("/api/projects/proj_test/town", json={
        "id": "draft", "name": "Incomplete", "archetype": "residential", "size_m": 200,
        "focal_venue_id": "missing", "venues": [],
    })
    assert response.status_code == 422
    assert not (tmp_path / ".data" / "proj_test" / "town.json").exists()
