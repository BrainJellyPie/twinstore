"""Malformed layout geometry must be rejected before modifying a saved layout."""

from copy import deepcopy

import pytest
from fastapi.testclient import TestClient

from store_emulator.application.storage.io import read_json, write_json


@pytest.fixture
def layout(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    from store_emulator.server.main import app
    client = TestClient(app, raise_server_exceptions=False)
    root = tmp_path / ".data" / "proj_test"
    write_json(root / "metadata.json", {"name": "Test"})
    setup = client.post("/api/projects/proj_test/setups", json={"mode": "empty"}).json()
    url = f"/api/projects/proj_test/setups/{setup['id']}"
    store = {"id": "store", "name": "Test", "type": "cafe", "grid_size": [8, 6], "racks": [
        {"id": "entry", "type": "entrance", "shape": [[1]], "position": [0, 0]},
        {"id": "exit", "type": "exit", "shape": [[1]], "position": [7, 5]},
        {"id": "shelf", "type": "shelf", "shape": [[1]], "position": [2, 2]},
    ]}
    saved = client.put(url, json={"setup": {"store": store}})
    assert saved.status_code == 200, saved.text
    path = root / "setups" / f"{setup['id']}.json"
    return client, url, store, path


@pytest.mark.parametrize("change", [
    {"shape": [], "rotation": 90},
    {"shape": [[1, 1], [1]]},
    {"shape": [[1], [1, 1]]},
    *[{"slots": [{"block": block, "face": "N", "level": 1,
                   "items": [{"sku": "A", "name": "Product", "price": 100}]}]} for block in (-2, -1, 1)],
    *[{"locked_faces": [{"block": block, "face": "N"}]} for block in (-1, 1)],
])
def test_invalid_geometry_preserves_saved_layout(layout, change):
    client, url, store, path = layout
    before = read_json(path)
    store["racks"][2].update(change)

    response = client.put(url, json={"setup": {"store": store}})

    assert response.status_code == 422, response.text
    assert read_json(path) == before


def test_rotated_multicell_shape_and_valid_block_round_trip(layout):
    client, url, original, _ = layout
    store = deepcopy(original)
    store["racks"][2].update({"shape": [[1, 1], [1, 0]], "rotation": 90,
                               "locked_faces": [{"block": 2, "face": "S"}]})

    response = client.put(url, json={"setup": {"store": store}})

    assert response.status_code == 200, response.text
    rack = client.get(url).json()["store"]["racks"][2]
    assert rack["shape"] == [[1, 1], [1, 0]] and rack["rotation"] == 90
    assert rack["locked_faces"] == [{"block": 2, "face": "S"}]


def test_duplicate_fixture_id_is_rejected_without_writing(layout):
    client, url, store, path = layout
    before = read_json(path)
    store["racks"][2]["id"] = store["racks"][0]["id"]
    response = client.put(url, json={"setup": {"store": store}})
    assert response.status_code == 422, response.text
    assert read_json(path) == before


def test_duplicate_shelf_slot_is_rejected_without_writing(layout):
    client, url, store, path = layout
    before = read_json(path)
    store["racks"][2]["slots"] = [
        {"block": 0, "face": "N", "level": 1, "items": [{"sku": sku, "name": sku, "price": 100}]}
        for sku in ("A", "B")
    ]
    response = client.put(url, json={"setup": {"store": store}})
    assert response.status_code == 422, response.text
    assert read_json(path) == before


def test_one_sku_on_distinct_levels_is_valid(layout):
    client, url, store, _ = layout
    store["racks"][2]["slots"] = [
        {"block": 0, "face": "N", "level": level, "items": [{"sku": "A", "name": "Tea", "price": 100}]}
        for level in (1, 2)
    ]
    response = client.put(url, json={"setup": {"store": store}})
    assert response.status_code == 200, response.text
    assert len(client.get(url).json()["store"]["racks"][2]["slots"]) == 2


@pytest.mark.parametrize("size", [(0, 6), (8, 0), (-1, 6), (8, -1), (0, 0)])
def test_empty_layout_rejects_nonpositive_grid_without_writing(layout, size):
    client, url, store, path = layout
    before = read_json(path)
    store.update(grid_size=size, racks=[])
    response = client.put(url, json={"setup": {"store": store}})
    assert response.status_code == 422, response.text
    assert read_json(path) == before


@pytest.mark.parametrize("size", [(1, 1), (40, 40)])
def test_positive_empty_grid_can_be_saved(layout, size):
    client, url, store, _ = layout
    store.update(grid_size=size, racks=[])
    response = client.put(url, json={"setup": {"store": store}})
    assert response.status_code == 200, response.text
    assert client.get(url).json()["store"]["grid_size"] == list(size)
