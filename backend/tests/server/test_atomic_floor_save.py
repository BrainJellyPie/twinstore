"""Confirmed floor replacements discard products only with the validated new floor."""
import copy

import pytest
from fastapi.testclient import TestClient

from store_emulator.application.storage.io import write_json
from store_emulator.application.storage.setups import metadata_path, new_setup_data, read_setup, setup_path
from store_emulator.domain.rack import Rack, Slot, SlotItem
from store_emulator.domain.store import Store

PID, SID = "proj_floor", "setup_floor"
URL = f"/api/projects/{PID}/setups/{SID}"


@pytest.fixture
def floor(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    store = Store(id="store", name="Floor", type="convenience", grid_size=(8, 8), racks=[
        Rack(id="in", type="entrance", shape=[[1]], position=(0, 7)),
        Rack(id="out", type="exit", shape=[[1]], position=(7, 7)),
        Rack(id="till", type="counter", shape=[[1]], position=(7, 0)),
        Rack(id="shelf", type="shelf", shape=[[1]], position=(3, 3), slots=[
            Slot(block=0, face="S", level=1, items=[SlotItem(sku="tea", name="Tea", price=100)]),
        ]),
    ])
    source = new_setup_data("Floor", None, store.model_dump(mode="json"))
    source["id"] = SID
    write_json(metadata_path(PID), {"name": "Floor", "currency": "USD"})
    write_json(setup_path(PID, SID), source)
    replacement = copy.deepcopy(source["store"])
    replacement["grid_size"] = [9, 8]
    for rack in replacement["racks"]:
        for slot in rack["slots"]:
            slot["items"] = []
    from store_emulator.server.main import app
    return TestClient(app, raise_server_exceptions=False), source, replacement


def test_confirmed_replacement_saves_floor_and_product_removal_together(floor):
    client, _, replacement = floor
    response = client.put(URL, json={"setup": {"store": replacement, "discard_products": True}})
    assert response.status_code == 200, response.text
    saved = read_setup(PID, SID)
    assert saved["store"] == replacement
    assert "discard_products" not in saved


@pytest.mark.parametrize("failure,expected", [
    ("unconfirmed", 409), ("invalid_floor", 422), ("still_has_products", 422),
    ("missing_floor", 422), ("running", 409), ("history", 409),
])
def test_rejected_floor_replacement_keeps_original_products_and_floor(floor, failure, expected):
    client, source, replacement = floor
    payload = {"store": replacement, "discard_products": True}
    if failure == "unconfirmed":
        payload.pop("discard_products")
    elif failure == "invalid_floor":
        replacement["racks"][-1]["position"] = [20, 20]
    elif failure == "still_has_products":
        replacement["racks"][-1]["slots"] = source["store"]["racks"][-1]["slots"]
    elif failure == "missing_floor":
        payload.pop("store")
    elif failure == "running":
        source["status"] = "running"
    else:
        source.update(status="locked", runId="run_previous")
    write_json(setup_path(PID, SID), source)
    before = setup_path(PID, SID).read_bytes()
    response = client.put(URL, json={"setup": payload})
    assert response.status_code == expected, response.text
    assert setup_path(PID, SID).read_bytes() == before


@pytest.mark.parametrize("flag", [1, "true", None])
def test_discard_confirmation_requires_a_boolean(floor, flag):
    client, source, replacement = floor
    response = client.put(URL, json={"setup": {"store": replacement, "discard_products": flag}})
    assert response.status_code == 422, response.text
    assert read_setup(PID, SID) == source
