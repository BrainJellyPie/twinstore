"""Product variants commit against one current source, including operating settings."""

import pytest
from fastapi.testclient import TestClient

from store_emulator.application import product_edits, setups, starter_fill
from store_emulator.application.storage.io import write_json
from store_emulator.application.storage.setups import read_setup, setup_path
from store_emulator.domain.operations import OperationsConfig
from store_emulator.server.main import app
from tests.server.test_shelf_lab_start_snapshot import overlap
from tests.server.test_simulation_setup_races import PID, SID, layout


@pytest.fixture(params=["products", "starter"])
def draft(layout, request):
    source = read_setup(PID, SID)
    rack = next(r for r in source["store"]["racks"] if any(s["items"] for s in r["slots"]))
    sku = next(i["sku"] for s in rack["slots"] for i in s["items"])
    kind = request.param
    if kind == "starter":
        rack["slots"] = []
        write_json(setup_path(PID, SID), source)
    module = product_edits if kind == "products" else starter_fill
    client = TestClient(app)
    url = f"/api/projects/{PID}/setups/{SID}/" + ("product-edits" if kind == "products" else "starter-fill")
    catalog = client.get(url)
    assert catalog.status_code == 200, catalog.text
    body = {"source_sha256": catalog.json()["source_sha256"], "currency": catalog.json()["currency"],
            "request_id": "f" * 32}
    if kind == "products":
        body["edits"] = [{"sku": sku, "name": "Explicit edit"}]
    else:
        body["assignments"] = [{"rack_id": rack["id"], "category": "home_coffee_tea"}]
    return client, url, body, module, kind


@pytest.mark.parametrize("change", ["store", "operations"])
@pytest.mark.parametrize("phase", ["prepared", "editor_first"])
def test_child_uses_a_current_source_without_mixing_snapshots(draft, monkeypatch, change, phase):
    client, url, body, module, kind = draft
    operations = OperationsConfig(stock_per_facing=77, backroom_per_product=19)

    def edit():
        if change == "operations":
            return setups.save_layout_operations(PID, SID, operations)
        store = read_setup(PID, SID)["store"]
        store["name"] = "Changed source floor"
        return setups.save_setup_with_lock(PID, SID, {"store": store})

    save = lambda: client.post(url + "/save", json=body)
    if phase == "prepared":
        response, _ = overlap(monkeypatch, module, "new_setup_data", save, edit)
    else:
        _, response = overlap(monkeypatch, setups, "write_setup", edit, save)
    expected = 409 if change == "store" else 200
    assert response.status_code == expected, response.text
    path = setup_path(PID, f"setup_{kind}_" + body["request_id"])
    if change == "store":
        assert not path.exists()
        receipt_kind = "product-edits" if kind == "products" else "starter-fill"
        assert not (path.parent / f".{receipt_kind}" / f"{body['request_id']}.json").exists()
    else:
        assert read_setup(PID, response.json()["setup_id"])["operations"] == operations.model_dump(mode="json")
        assert client.post(url + "/save", json=body).json() == response.json()
