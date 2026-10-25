"""Applying a reviewed variant preserves its identity in the saved child layout."""

import pytest

from store_emulator.application.storage.io import write_json
from store_emulator.application.storage.setups import read_setup, setup_path
from store_emulator.domain.capture import CaptureItem, CaptureResult
from store_emulator.engine.layout_gen import generate_store
from tests.server.test_shelf_lab_start_snapshot import CID, lab
from tests.server.test_simulation_setup_races import PID, SID, layout


@pytest.mark.parametrize("new_rack", [False, True])
@pytest.mark.parametrize("estimated", [False, True])
def test_saved_child_keeps_variant_sku_name_and_price(lab, new_rack, estimated):
    client, _, _, folder = lab
    store = generate_store("mini_mart")
    rack = next(r for r in store.product_racks if r.slots)
    sku = rack.slots[0].items[0].sku
    for _, slot in store.all_slots:
        for item in slot.items:
            if item.sku == sku:
                item.name = "TwinStore Original Cola 500ml"
                item.price = 100
    data = read_setup(PID, SID)
    write_json(setup_path(PID, SID), {**data, "store": store.model_dump(mode="json")})
    capture = CaptureResult(image_size=(160, 160), currency="USD", items=[CaptureItem(
        id="i1", band=0, level=1, order=0, sku="cap_distinct", name="TwinStore Original Cola 1500ml",
        price=399, price_estimated=estimated, labeled=True, category="soft_drinks",
    )])
    write_json(folder / "result.json", capture.model_dump(mode="json"))
    before = setup_path(PID, SID).read_bytes()
    response = client.post(f"/api/projects/{PID}/captures/{CID}/apply", json={
        "setup_id": SID, "rack_id": rack.id, "face": rack.slots[0].face.value, "new_rack": new_rack,
    })
    assert response.status_code == 200, response.text
    body = response.json()
    child = read_setup(PID, body["setup_id"])
    placed = [item for saved in child["store"]["racks"] if saved["id"] in body["rack_ids"]
              for slot in saved["slots"] for item in slot["items"] if item["sku"] == "cap_distinct"]
    assert placed and all((item["name"], item["price"]) == ("TwinStore Original Cola 1500ml", 399) for item in placed)
    assert setup_path(PID, SID).read_bytes() == before
    assert child["parentId"] == SID
